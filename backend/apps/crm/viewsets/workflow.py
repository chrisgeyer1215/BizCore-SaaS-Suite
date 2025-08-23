"""
CRM Workflow ViewSets - Business Process Automation
Provides workflow rules, automation triggers, and process management
"""

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Q, Count
from django.utils import timezone
from datetime import datetime, timedelta
import json

from ..models import (
    WorkflowRule, WorkflowExecution, Integration, 
    WebhookConfiguration, Activity, Lead, Opportunity
)
from ..serializers.workflow import (
    WorkflowRuleSerializer, WorkflowExecutionSerializer,
    IntegrationSerializer, WebhookConfigurationSerializer
)
from ..permissions.workflow import (
    CanManageWorkflows, CanViewWorkflowExecutions,
    CanManageIntegrations, CanManageWebhooks
)
from ..services.workflow_service import WorkflowService
from ..utils.tenant_utils import get_tenant_context


class WorkflowRuleViewSet(viewsets.ModelViewSet):
    """
    Workflow Rules Management ViewSet
    Handles business process automation rules and triggers
    """
    serializer_class = WorkflowRuleSerializer
    permission_classes = [IsAuthenticated, CanManageWorkflows]
    
    def get_queryset(self):
        tenant = get_tenant_context(self.request)
        return WorkflowRule.objects.filter(
            tenant=tenant,
            is_deleted=False
        ).select_related('created_by', 'modified_by')
    
    def perform_create(self, serializer):
        tenant = get_tenant_context(self.request)
        serializer.save(
            tenant=tenant,
            created_by=self.request.user
        )
    
    @action(detail=True, methods=['post'])
    def activate(self, request, pk=None):
        """Activate workflow rule"""
        workflow = self.get_object()
        
        try:
            service = WorkflowService(tenant=workflow.tenant)
            result = service.activate_workflow(
                workflow=workflow,
                user=request.user
            )
            
            return Response({
                'success': True,
                'message': 'Workflow activated successfully',
                'workflow_id': workflow.id,
                'status': 'active'
            })
        except Exception as e:
            return Response({
                'success': False,
                'error': f"Activation failed: {str(e)}"
            }, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['post'])
    def deactivate(self, request, pk=None):
        """Deactivate workflow rule"""
        workflow = self.get_object()
        
        try:
            service = WorkflowService(tenant=workflow.tenant)
            result = service.deactivate_workflow(
                workflow=workflow,
                user=request.user
            )
            
            return Response({
                'success': True,
                'message': 'Workflow deactivated successfully',
                'workflow_id': workflow.id,
                'status': 'inactive'
            })
        except Exception as e:
            return Response({
                'success': False,
                'error': f"Deactivation failed: {str(e)}"
            }, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['post'])
    def test(self, request, pk=None):
        """Test workflow rule with sample data"""
        workflow = self.get_object()
        test_data = request.data
        
        try:
            service = WorkflowService(tenant=workflow.tenant)
            test_result = service.test_workflow(
                workflow=workflow,
                test_data=test_data,
                user=request.user
            )
            
            return Response({
                'success': True,
                'test_result': test_result,
                'conditions_met': test_result.get('conditions_met'),
                'actions_executed': test_result.get('actions_executed'),
                'execution_time': test_result.get('execution_time')
            })
        except Exception as e:
            return Response({
                'success': False,
                'error': f"Workflow test failed: {str(e)}"
            }, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['get'])
    def executions(self, request, pk=None):
        """Get workflow execution history"""
        workflow = self.get_object()
        
        executions = WorkflowExecution.objects.filter(
            workflow=workflow
        ).order_by('-executed_at')[:100]
        
        serializer = WorkflowExecutionSerializer(executions, many=True)
        
        return Response({
            'success': True,
            'executions': serializer.data,
            'total_executions': executions.count(),
            'success_rate': workflow.success_rate
        })
    
    @action(detail=False, methods=['get'])
    def templates(self, request):
        """Get workflow rule templates"""
        templates = [
            {
                'id': 'lead_assignment',
                'name': 'Auto Lead Assignment',
                'description': 'Automatically assign leads based on criteria',
                'trigger': 'lead_created',
                'conditions': [
                    {'field': 'lead_source', 'operator': 'equals', 'value': 'website'},
                    {'field': 'country', 'operator': 'equals', 'value': 'US'}
                ],
                'actions': [
                    {'type': 'assign_to_user', 'user_id': 'round_robin'},
                    {'type': 'send_email', 'template': 'lead_assignment_notification'}
                ]
            },
            {
                'id': 'opportunity_follow_up',
                'name': 'Opportunity Follow-up',
                'description': 'Create follow-up tasks for stale opportunities',
                'trigger': 'scheduled',
                'schedule': 'daily',
                'conditions': [
                    {'field': 'stage', 'operator': 'not_equals', 'value': 'closed_won'},
                    {'field': 'last_activity_date', 'operator': 'older_than', 'value': '7_days'}
                ],
                'actions': [
                    {'type': 'create_task', 'subject': 'Follow up on opportunity'},
                    {'type': 'send_email', 'template': 'opportunity_follow_up'}
                ]
            },
            {
                'id': 'deal_escalation',
                'name': 'Deal Escalation',
                'description': 'Escalate high-value deals approaching close date',
                'trigger': 'opportunity_updated',
                'conditions': [
                    {'field': 'value', 'operator': 'greater_than', 'value': 100000},
                    {'field': 'close_date', 'operator': 'within_days', 'value': 7}
                ],
                'actions': [
                    {'type': 'notify_manager', 'priority': 'high'},
                    {'type': 'create_activity', 'type': 'call', 'priority': 'high'}
                ]
            }
        ]
        
        return Response({
            'success': True,
            'templates': templates
        })


class WorkflowExecutionViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Workflow Execution ViewSet
    Read-only access to workflow execution logs and analytics
    """
    serializer_class = WorkflowExecutionSerializer
    permission_classes = [IsAuthenticated, CanViewWorkflowExecutions]
    
    def get_queryset(self):
        tenant = get_tenant_context(self.request)
        return WorkflowExecution.objects.filter(
            tenant=tenant
        ).select_related('workflow', 'executed_by').order_by('-executed_at')
    
    @action(detail=False, methods=['get'])
    def analytics(self, request):
        """Get workflow execution analytics"""
        tenant = get_tenant_context(request)
        date_range = int(request.query_params.get('date_range', 30))
        
        try:
            service = WorkflowService(tenant=tenant)
            analytics = service.get_execution_analytics(
                date_range=date_range,
                workflow_id=request.query_params.get('workflow_id')
            )
            
            return Response({
                'success': True,
                'analytics': analytics,
                'date_range': f"Last {date_range} days"
            })
        except Exception as e:
            return Response({
                'success': False,
                'error': f"Analytics failed: {str(e)}"
            }, status=status.HTTP_400_BAD_REQUEST)


class IntegrationViewSet(viewsets.ModelViewSet):
    """
    Integration Management ViewSet
    Handles third-party system integrations
    """
    serializer_class = IntegrationSerializer
    permission_classes = [IsAuthenticated, CanManageIntegrations]
    
    def get_queryset(self):
        tenant = get_tenant_context(self.request)
        return Integration.objects.filter(
            tenant=tenant,
            is_active=True
        )
    
    def perform_create(self, serializer):
        tenant = get_tenant_context(self.request)
        serializer.save(
            tenant=tenant,
            created_by=self.request.user
        )
    
    @action(detail=True, methods=['post'])
    def test_connection(self, request, pk=None):
        """Test integration connection"""
        integration = self.get_object()
        
        try:
            service = WorkflowService(tenant=integration.tenant)
            test_result = service.test_integration_connection(
                integration=integration,
                user=request.user
            )
            
            return Response({
                'success': True,
                'connection_status': test_result.get('status'),
                'response_time': test_result.get('response_time'),
                'last_tested': timezone.now().isoformat()
            })
        except Exception as e:
            return Response({
                'success': False,
                'error': f"Connection test failed: {str(e)}"
            }, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['post'])
    def sync_data(self, request, pk=None):
        """Trigger data synchronization"""
        integration = self.get_object()
        sync_type = request.data.get('sync_type', 'full')
        
        try:
            service = WorkflowService(tenant=integration.tenant)
            sync_result = service.sync_integration_data(
                integration=integration,
                sync_type=sync_type,
                user=request.user
            )
            
            return Response({
                'success': True,
                'sync_id': sync_result.get('sync_id'),
                'status': 'started',
                'estimated_completion': sync_result.get('estimated_completion')
            })
        except Exception as e:
            return Response({
                'success': False,
                'error': f"Sync failed: {str(e)}"
            }, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['get'])
    def available_integrations(self, request):
        """Get list of available integrations"""
        integrations = [
            {
                'type': 'email_marketing',
                'name': 'Email Marketing Platforms',
                'providers': ['mailchimp', 'sendgrid', 'hubspot', 'constant_contact'],
                'capabilities': ['sync_contacts', 'campaign_tracking', 'email_automation']
            },
            {
                'type': 'calendar',
                'name': 'Calendar Systems',
                'providers': ['google_calendar', 'outlook', 'calendly'],
                'capabilities': ['sync_events', 'meeting_scheduling', 'availability_checking']
            },
            {
                'type': 'communication',
                'name': 'Communication Tools',
                'providers': ['zoom', 'slack', 'teams', 'whatsapp'],
                'capabilities': ['meeting_integration', 'chat_sync', 'notification_delivery']
            },
            {
                'type': 'accounting',
                'name': 'Accounting Systems',
                'providers': ['quickbooks', 'xero', 'freshbooks'],
                'capabilities': ['invoice_sync', 'payment_tracking', 'financial_reporting']
            },
            {
                'type': 'social_media',
                'name': 'Social Media Platforms',
                'providers': ['linkedin', 'twitter', 'facebook', 'instagram'],
                'capabilities': ['lead_generation', 'social_listening', 'campaign_tracking']
            }
        ]
        
        return Response({
            'success': True,
            'integrations': integrations
        })


class WebhookConfigurationViewSet(viewsets.ModelViewSet):
    """
    Webhook Configuration ViewSet
    Manages incoming and outgoing webhooks
    """
    serializer_class = WebhookConfigurationSerializer
    permission_classes = [IsAuthenticated, CanManageWebhooks]
    
    def get_queryset(self):
        tenant = get_tenant_context(self.request)
        return WebhookConfiguration.objects.filter(
            tenant=tenant,
            is_active=True
        )
    
    def perform_create(self, serializer):
        tenant = get_tenant_context(self.request)
        serializer.save(
            tenant=tenant,
            created_by=self.request.user
        )
    
    @action(detail=True, methods=['post'])
    def test_webhook(self, request, pk=None):
        """Test webhook configuration"""
        webhook = self.get_object()
        test_payload = request.data.get('test_payload', {})
        
        try:
            service = WorkflowService(tenant=webhook.tenant)
            test_result = service.test_webhook(
                webhook=webhook,
                test_payload=test_payload,
                user=request.user
            )
            
            return Response({
                'success': True,
                'test_result': test_result,
                'response_code': test_result.get('response_code'),
                'response_time': test_result.get('response_time'),
                'payload_sent': test_payload
            })
        except Exception as e:
            return Response({
                'success': False,
                'error': f"Webhook test failed: {str(e)}"
            }, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['get'])
    def delivery_logs(self, request, pk=None):
        """Get webhook delivery logs"""
        webhook = self.get_object()
        
        try:
            service = WorkflowService(tenant=webhook.tenant)
            logs = service.get_webhook_delivery_logs(
                webhook=webhook,
                limit=int(request.query_params.get('limit', 100)),
                status_filter=request.query_params.get('status')
            )
            
            return Response({
                'success': True,
                'logs': logs,
                'webhook_id': webhook.id,
                'total_deliveries': len(logs)
            })
        except Exception as e:
            return Response({
                'success': False,
                'error': f"Log retrieval failed: {str(e)}"
            }, status=status.HTTP_400_BAD_REQUEST)