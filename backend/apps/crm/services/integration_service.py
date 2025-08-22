# ============================================================================
# backend/apps/crm/services/integration_service.py - External Integration Service
# ============================================================================

from typing import Dict, List, Any, Optional
from django.db import transaction
from django.utils import timezone
from django.core.cache import cache
import requests
import json
import hashlib
from datetime import timedelta

from .base import BaseService, CacheableMixin, CRMServiceException
from ..models import Integration, SyncLog, APIUsageLog


class IntegrationService(BaseService, CacheableMixin):
    """Service for managing external integrations and data synchronization"""
    
    def __init__(self, tenant, user=None):
        super().__init__(tenant, user)
        self.supported_integrations = self._get_supported_integrations()
    
    @transaction.atomic
    def create_integration(self, integration
        """Create new external integration"""
        
        self.require_permission('can_manage_integrations')
        
        integration_type = integration_data.get('integration_type')
        if integration_type not in self.supported_integrations:
            raise CRMServiceException(f"Unsupported integration type: {integration_type}")
        
        # Validate configuration
        self._validate_integration_config(integration_data)
        
        integration_data.update({
            'tenant': self.tenant,
            'created_by': self.user,
        })
        
        integration = Integration.objects.create(**integration_data)
        
        # Test connection
        test_result = self.test_integration_connection(integration.id)
        if not test_result.get('success'):
            integration.status = 'ERROR'
            integration.error_message = test_result.get('error', 'Connection test failed')
            integration.save()
        
        self.logger.info(f"Integration created: {integration.name} ({integration.integration_type})")
        return integration
    
    def test_integration_connection(self, integration_id: int) -> Dict:
        """Test integration connection and authentication"""
        
        try:
            integration = Integration.objects.get(id=integration_id, tenant=self.tenant)
            
            if integration.integration_type == 'EMAIL_PROVIDER':
                return self._test_email_provider_connection(integration)
            elif integration.integration_type == 'CRM_SYSTEM':
                return self._test_crm_system_connection(integration)
            elif integration.integration_type == 'ACCOUNTING_SYSTEM':
                return self._test_accounting_system_connection(integration)
            elif integration.integration_type == 'MARKETING_PLATFORM':
                return self._test_marketing_platform_connection(integration)
            elif integration.integration_type == 'SOCIAL_MEDIA':
                return self._test_social_media_connection(integration)
            else:
                return self._test_generic_api_connection(integration)
                
        except Integration.DoesNotExist:
            return {'success': False, 'error': 'Integration not found'}
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    @transaction.atomic
    def synchronize_data(self, integration_id: int, sync_config: Dict = None) -> Dict:
        """Synchronize data with external system"""
        
        integration = Integration.objects.get(id=integration_id, tenant=self.tenant)
        
        if not integration.is_active:
            raise CRMServiceException("Integration is not active")
        
        sync_log = SyncLog.objects.create(
            tenant=self.tenant,
            integration_name=integration.name,
            sync_type=sync_config.get('sync_type', 'BIDIRECTIONAL'),
            status='RUNNING',
            sync_data=sync_config or {}
        )
        
        try:
            if integration.integration_type == 'EMAIL_PROVIDER':
                result = self._sync_email_provider_data(integration, sync_config)
            elif integration.integration_type == 'CRM_SYSTEM':
                result = self._sync_crm_system_data(integration, sync_config)
            elif integration.integration_type == 'ACCOUNTING_SYSTEM':
                result = self._sync_accounting_system_data(integration, sync_config)
            elif integration.integration_type == 'MARKETING_PLATFORM':
                result = self._sync_marketing_platform_data(integration, sync_config)
            else:
                result = self._sync_generic_system_data(integration, sync_config)
            
            # Update sync log
            sync_log.status = 'COMPLETED'
            sync_log.records_processed = result.get('records_processed', 0)
            sync_log.records_successful = result.get('records_successful', 0)
            sync_log.records_failed = result.get('records_failed', 0)
            sync_log.sync_data.update(result)
            sync_log.save()
            
            # Update integration last sync time
            integration.last_sync = timezone.now()
            integration.save()
            
            return result
            
        except Exception as e:
            sync_log.status = 'FAILED'
            sync_log.error_details = {'error': str(e)}
            sync_log.save()
            
            self.logger.error(f"Sync failed for integration {integration.name}: {str(e)}")
            raise CRMServiceException(f"Synchronization failed: {str(e)}")
    
    def import_data_from_integration(self, integration_id: int, 
                                   import_config: Dict) -> Dict:
        """Import data from external system"""
        
        integration = Integration.objects.get(id=integration_id, tenant=self.tenant)
        data_type = import_config.get('data_type')
        
        if data_type == 'leads':
            return self._import_leads_from_integration(integration, import_config)
        elif data_type == 'accounts':
            return self._import_accounts_from_integration(integration, import_config)
        elif data_type == 'contacts':
            return self._import_contacts_from_integration(integration, import_config)
        elif data_type == 'opportunities':
            return self._import_opportunities_from_integration(integration, import_config)
        else:
            raise CRMServiceException(f"Unsupported import data type: {data_type}")
    
    def export_data_to_integration(self, integration_id: int, 
                                  export_config: Dict) -> Dict:
        """Export data to external system"""
        
        integration = Integration.objects.get(id=integration_id, tenant=self.tenant)
        data_type = export_config.get('data_type')
        
        if data_type == 'leads':
            return self._export_leads_to_integration(integration, export_config)
        elif data_type == 'accounts':
            return self._export_accounts_to_integration(integration, export_config)
        elif data_type == 'contacts':
            return self._export_contacts_to_integration(integration, export_config)
        elif data_type == 'opportunities':
            return self._export_opportunities_to_integration(integration, export_config)
        else:
            raise CRMServiceException(f"Unsupported export data type: {data_type}")
    
    def handle_webhook(self, integration_id: int, webhook_data: Dict, 
                      headers: Dict = None) -> Dict:
        """Handle incoming webhook from external system"""
        
        try:
            integration = Integration.objects.get(id=integration_id, tenant=self.tenant)
            
            # Verify webhook signature if configured
            if integration.webhook_secret:
                if not self._verify_webhook_signature(webhook_data, headers, integration.webhook_secret):
                    raise CRMServiceException("Invalid webhook signature")
            
            # Process webhook based on integration type
            if integration.integration_type == 'EMAIL_PROVIDER':
                return self._handle_email_provider_webhook(integration, webhook_data)
            elif integration.integration_type == 'MARKETING_PLATFORM':
                return self._handle_marketing_platform_webhook(integration, webhook_data)
            elif integration.integration_type == 'PAYMENT_PROCESSOR':
                return self._handle_payment_processor_webhook(integration, webhook_data)
            else:
                return self._handle_generic_webhook(integration, webhook_data)
                
        except Integration.DoesNotExist:
            raise CRMServiceException("Integration not found")
    
    def get_integration_analytics(self, integration_id: int = None, 
                                 date_range: Dict = None) -> Dict:
        """Get comprehensive integration analytics"""
        
        sync_logs = SyncLog.objects.filter(tenant=self.tenant)
        api_logs = APIUsageLog.objects.filter(tenant=self.tenant)
        
        if integration_id:
            integration = Integration.objects.get(id=integration_id, tenant=self.tenant)
            sync_logs = sync_logs.filter(integration_name=integration.name)
        
        if date_range:
            if date_range.get('start_date'):
                sync_logs = sync_logs.filter(created_at__gte=date_range['start_date'])
                api_logs = api_logs.filter(created_at__gte=date_range['start_date'])
            if date_range.get('end_date'):
                sync_logs = sync_logs.filter(created_at__lte=date_range['end_date'])
                api_logs = api_logs.filter(created_at__lte=date_range['end_date'])
        
        # Sync statistics
        sync_stats = {
            'total_syncs': sync_logs.count(),
            'successful_syncs': sync_logs.filter(status='COMPLETED').count(),
            'failed_syncs': sync_logs.filter(status='FAILED').count(),
            'total_records_processed': sync_logs.aggregate(
                total=models.Sum('records_processed')
            )['total'] or 0,
            'total_records_successful': sync_logs.aggregate(
                total=models.Sum('records_successful')
            )['total'] or 0,
        }
        
        if sync_stats['total_syncs'] > 0:
            sync_stats['success_rate'] = (sync_stats['successful_syncs'] / sync_stats['total_syncs']) * 100
        
        # API usage statistics
        api_stats = {
            'total_requests': api_logs.count(),
            'successful_requests': api_logs.filter(status_code__lt=400).count(),
            'failed_requests': api_logs.filter(status_code__gte=400).count(),
            'average_response_time': api_logs.aggregate(
                avg=models.Avg('response_time_ms')
            )['avg'] or 0,
        }
        
        # Integration performance by type
        integration_performance = Integration.objects.filter(
            tenant=self.tenant
        ).values('integration_type', 'name').annotate(
            sync_count=models.Count('synclog'),
            success_rate=models.Avg(
                models.Case(
                    models.When(synclog__status='COMPLETED', then=100),
                    models.When(synclog__status='FAILED', then=0),
                    default=50,
                    output_field=models.FloatField()
                )
            )
        )
        
        # Recent sync activity
        recent_syncs = sync_logs.order_by('-created_at')[:10].values(
            'integration_name', 'sync_type', 'status', 'records_processed', 'created_at'
        )
        
        return {
            'sync_statistics': sync_stats,
            'api_statistics': api_stats,
            'integration_performance': list(integration_performance),
            'recent_activity': list(recent_syncs),
        }
    
    def _validate_integration_config(self
        
        integration_type = integration_data.get('integration_type')
        config = integration_data.get('config', {})
        
        if integration_type == 'EMAIL_PROVIDER':
            required_fields = ['api_key', 'base_url']
        elif integration_type == 'CRM_SYSTEM':
            required_fields = ['api_key', 'instance_url']
        elif integration_type == 'ACCOUNTING_SYSTEM':
            required_fields = ['client_id', 'client_secret', 'base_url']
        elif integration_type == 'MARKETING_PLATFORM':
            required_fields = ['api_key', 'list_id']
        else:
            required_fields = ['api_key', 'base_url']
        
        for field in required_fields:
            if not config.get(field):
                raise CRMServiceException(f"Missing required configuration field: {field}")
    
    def _test_email_provider_connection(self, integration: Integration) -> Dict:
        """Test email provider connection"""
        
        config = integration.config
        
        try:
            # Test API connection (example for SendGrid)
            headers = {
                'Authorization': f"Bearer {config.get('api_key')}",
                'Content-Type': 'application/json'
            }
            
            response = requests.get(
                f"{config.get('base_url')}/user/profile",
                headers=headers,
                timeout=30
            )
            
            if response.status_code == 200:
                return {'success': True, 'message': 'Connection successful'}
            else:
                return {'success': False, 'error': f'API returned status {response.status_code}'}
                
        except requests.RequestException as e:
            return {'success': False, 'error': str(e)}
    
    def _test_crm_system_connection(self, integration: Integration) -> Dict:
        """Test CRM system connection (e.g., Salesforce)"""
        
        config = integration.config
        
        try:
            # Test OAuth or API key authentication
            headers = {
                'Authorization': f"Bearer {config.get('api_key')}",
                'Content-Type': 'application/json'
            }
            
            response = requests.get(
                f"{config.get('instance_url')}/services/data/v52.0/",
                headers=headers,
                timeout=30
            )
            
            if response.status_code == 200:
                return {'success': True, 'message': 'Connection successful'}
            else:
                return {'success': False, 'error': f'API returned status {response.status_code}'}
                
        except requests.RequestException as e:
            return {'success': False, 'error': str(e)}
    
    def _test_accounting_system_connection(self, integration: Integration) -> Dict:
        """Test accounting system connection (e.g., QuickBooks)"""
        
        config = integration.config
        
        try:
            # Test OAuth connection
            auth_data = {
                'client_id': config.get('client_id'),
                'client_secret': config.get('client_secret'),
                'grant_type': 'client_credentials'
            }
            
            response = requests.post(
                f"{config.get('base_url')}/oauth2/token",
                data=auth_data,
                timeout=30
            )
            
            if response.status_code == 200:
                return {'success': True, 'message': 'Connection successful'}
            else:
                return {'success': False, 'error': f'Auth failed with status {response.status_code}'}
                
        except requests.RequestException as e:
            return {'success': False, 'error': str(e)}
    
    def _test_marketing_platform_connection(self, integration: Integration) -> Dict:
        """Test marketing platform connection (e.g., Mailchimp)"""
        
        config = integration.config
        
        try:
            headers = {
                'Authorization': f"apikey {config.get('api_key')}",
                'Content-Type': 'application/json'
            }
            
            response = requests.get(
                f"{config.get('base_url')}/3.0/ping",
                headers=headers,
                timeout=30
            )
            
            if response.status_code == 200:
                return {'success': True, 'message': 'Connection successful'}
            else:
                return {'success': False, 'error': f'API returned status {response.status_code}'}
                
        except requests.RequestException as e:
            return {'success': False, 'error': str(e)}
    
    def _test_social_media_connection(self, integration: Integration) -> Dict:
        """Test social media API connection"""
        
        config = integration.config
        platform = config.get('platform', '').lower()
        
        try:
            if platform == 'linkedin':
                headers = {
                    'Authorization': f"Bearer {config.get('access_token')}",
                    'Content-Type': 'application/json'
                }
                
                response = requests.get(
                    "https://api.linkedin.com/v2/me",
                    headers=headers,
                    timeout=30
                )
                
            elif platform == 'twitter':
                headers = {
                    'Authorization': f"Bearer {config.get('bearer_token')}",
                    'Content-Type': 'application/json'
                }
                
                response = requests.get(
                    "https://api.twitter.com/2/users/me",
                    headers=headers,
                    timeout=30
                )
                
            else:
                return {'success': False, 'error': f'Unsupported social platform: {platform}'}
            
            if response.status_code == 200:
                return {'success': True, 'message': 'Connection successful'}
            else:
                return {'success': False, 'error': f'API returned status {response.status_code}'}
                
        except requests.RequestException as e:
            return {'success': False, 'error': str(e)}
    
    def _test_generic_api_connection(self, integration: Integration) -> Dict:
        """Test generic API connection"""
        
        config = integration.config
        
        try:
            headers = {
                'Authorization': f"Bearer {config.get('api_key')}",
                'Content-Type': 'application/json'
            }
            
            test_endpoint = config.get('test_endpoint', '/health')
            response = requests.get(
                f"{config.get('base_url')}{test_endpoint}",
                headers=headers,
                timeout=30
            )
            
            if response.status_code in [200, 201]:
                return {'success': True, 'message': 'Connection successful'}
            else:
                return {'success': False, 'error': f'API returned status {response.status_code}'}
                
        except requests.RequestException as e:
            return {'success': False, 'error': str(e)}
    
    def _sync_email_provider_data(self, integration: Integration, sync_config: Dict) -> Dict:
        """Synchronize data with email provider"""
        
        # This would implement specific sync logic for email providers
        # Example: sync email engagement data, lists, campaigns, etc.
        
        return {
            'records_processed': 0,
            'records_successful': 0,
            'records_failed': 0,
            'sync_type': 'email_provider_sync'
        }
    
    def _import_leads_from_integration(self, integration: Integration, 
                                     import_config: Dict) -> Dict:
        """Import leads from external system"""
        
        from .lead_service import LeadService
        
        lead_service = LeadService(self.tenant, self.user)
        
        # Fetch leads from external system
        external_leads = self._fetch_external_data(integration, 'leads', import_config)
        
        imported_count = 0
        failed_count = 0
        errors = []
        
        for external_lead in external_leads:
            try:
                # Transform external lead data to CRM format
                lead_data = self._transform_lead_data(external_lead, integration)
                
                # Create lead using lead service
                lead = lead_service.create_lead(lead_data)
                imported_count += 1
                
            except Exception as e:
                failed_count += 1
                errors.append({
                    'external_id': external_lead.get('id'),
                    'error': str(e)
                })
        
        return {
            'imported_count': imported_count,
            'failed_count': failed_count,
            'total_processed': len(external_leads),
            'errors': errors
        }
    
    def _fetch_external_data(self, integration: Integration, data_type: str, 
                           config: Dict) -> List[Dict]:
        """Fetch data from external system"""
        
        # This would implement the actual API calls to fetch data
        # For now, return empty list as placeholder
        
        return []
    
    def _transform_lead_data(self, external_lead: Dict, integration: Integration) -> Dict:
        """Transform external lead data to CRM format"""
        
        # Field mapping based on integration type
        field_mappings = integration.config.get('field_mappings', {})
        
        lead_data = {}
        for crm_field, external_field in field_mappings.items():
            if external_field in external_lead:
                lead_data[crm_field] = external_lead[external_field]
        
        return lead_data
    
    def _verify_webhook_signature(self, data: Dict, headers: Dict, secret: str) -> bool:
        """Verify webhook signature for security"""
        
        signature = headers.get('X-Webhook-Signature', '')
        if not signature:
            return False
        
        # Calculate expected signature
        payload = json.dumps(data, sort_keys=True)
        expected_signature = hashlib.sha256(
            f"{secret}{payload}".encode()
        ).hexdigest()
        
        return signature == expected_signature
    
    def _handle_email_provider_webhook(self, integration: Integration, 
                 -> Dict:
        """Handle webhook from email provider"""
        
        event_type = webhook_data.get('event_type')
        
        if event_type in ['delivered', 'opened', 'clicked', 'bounced', 'unsubscribed']:
            # Update email engagement tracking
            from .notification_service import NotificationService
            
            notification_service = NotificationService(self.tenant)
            
            email_id = webhook_data.get('email_id')
            if email_id:
                notification_service.track_email_engagement(
                    email_id, event_type.upper(), webhook_data
                )
        
        return {'status': 'processed', 'event_type': event_type}
    
    def _get_supported_integrations(self) -> Dict:
        """Get list of supported integration types"""
        
        return {
            'EMAIL_PROVIDER': 'Email Service Providers (SendGrid, Mailgun, etc.)',
            'CRM_SYSTEM': 'Other CRM Systems (Salesforce, HubSpot, etc.)',
            'ACCOUNTING_SYSTEM': 'Accounting Systems (QuickBooks, Xero, etc.)',
            'MARKETING_PLATFORM': 'Marketing Platforms (Mailchimp, Constant Contact, etc.)',
            'SOCIAL_MEDIA': 'Social Media Platforms (LinkedIn, Twitter, etc.)',
            'PAYMENT_PROCESSOR': 'Payment Processors (Stripe, PayPal, etc.)',
            'CALENDAR_SYSTEM': 'Calendar Systems (Google Calendar, Outlook, etc.)',
            'COMMUNICATION_TOOL': 'Communication Tools (Slack, Teams, etc.)',
            'ANALYTICS_PLATFORM': 'Analytics Platforms (Google Analytics, etc.)',
            'GENERIC_API': 'Generic REST API',
        }