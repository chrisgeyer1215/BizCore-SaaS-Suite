# ============================================================================
# backend/apps/crm/services/integration_service.py - Advanced Integration Management Service
# ============================================================================

import json
import requests
import hmac
import hashlib
import base64
from typing import Dict, List, Any, Optional, Tuple, Union, Callable
from datetime import datetime, timedelta
from decimal import Decimal
from django.db import transaction, models
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.conf import settings
from django.core.cache import cache
from django.template import Template, Context
import logging

from .base import BaseService, ServiceException
from ..models import (
    Integration, IntegrationConfig, IntegrationLog, DataSync, SyncMapping,
    WebhookEndpoint, APIKey, OAuthToken, DataTransform, IntegrationError,
    ExternalSystem, SyncJob, FieldMapping, DataValidationRule
)

logger = logging.getLogger(__name__)


class IntegrationException(ServiceException):
    """Integration service specific errors"""
    pass


class APIConnector:
    """Universal API connector for external systems"""
    
    def __init__(self, integration_config: Dict):
        self.config = integration_config
        self.session = requests.Session()
        self._setup_authentication()
    
    def _setup_authentication(self):
        """Setup authentication based on integration type"""
        auth_type = self.config.get('auth_type', 'none')
        
        if auth_type == 'api_key':
            api_key = self.config.get('api_key')
            key_header = self.config.get('api_key_header', 'Authorization')
            
            if api_key:
                if key_header.lower() == 'authorization':
                    self.session.headers.update({'Authorization': f"Bearer {api_key}"})
                else:
                    self.session.headers.update({key_header: api_key})
        
        elif auth_type == 'basic_auth':
            username = self.config.get('username')
            password = self.config.get('password')
            if username and password:
                self.session.auth = (username, password)
        
        elif auth_type == 'oauth2':
            access_token = self.config.get('access_token')
            if access_token:
                self.session.headers.update({
                    'Authorization': f"Bearer {access_token}"
                })
        
        # Set common headers
        self.session.headers.update({
            'Content-Type': 'application/json',
            'User-Agent': f"CRM-Integration/{settings.VERSION if hasattr(settings, 'VERSION') else '1.0'}"
        })
    
    def make_request(self, method: str None, 
                    params: Dict = None, headers: Dict = None) -> Dict:
        """Make authenticated API request"""
        try:
            url = f"{self.config.get('base_url', '').rstrip('/')}/{endpoint.lstrip('/')}"
            
            # Merge headers
            request_headers = self.session.headers.copy()
            if headers:
                request_headers.update(headers)
            
            # Rate limiting
            self._handle_rate_limiting()
            
            # Make request
            response = self.session.request(
                method=method.upper(),
                url=url,
                json=data if method.upper() in ['POST', 'PUT', 'PATCH'] else None,
                params=params,
                headers=request_headers,
                timeout=self.config.get('timeout', 30)
            )
            
            # Handle response
            if response.status_code >= 400:
                error_data = self._extract_error_data(response)
                raise IntegrationException(
                    f"API request failed: {response.status_code} - {error_data.get('message', 'Unknown error')}",
                    code=f'API_ERROR_{response.status_code}',
                    details=error_data
                )
            
            # Parse response
            if response.headers.get('content-type', '').startswith('application/json'):
                return response.json()
            else:
                return {'raw_response': response.text, 'status_code': response.status_code}
            
        except requests.RequestException as e:
            logger.error(f"API request failed: {e}", exc_info=True)
            raise IntegrationException(f"Network request failed: {str(e)}")
    
    def _handle_rate_limiting(self):
        """Handle API rate limiting"""
        rate_limit_key = f"api_rate_limit_{self.config.get('integration_id', 'unknown')}"
        
        # Simple rate limiting implementation
        current_count = cache.get(rate_limit_key, 0)
        rate_limit = self.config.get('rate_limit_per_minute', 60)
        
        if current_count >= rate_limit:
            raise IntegrationException(
                "Rate limit exceeded", 
                code='RATE_LIMIT_EXCEEDED',
                retry_after=60
            )
        
        cache.set(rate_limit_key, current_count + 1, 60)  # Reset every minute


class DataTransformer:
    """Advanced data transformation engine"""
    
    def __init__(self, tenant):
        self.tenant = tenant
        self.transformers = {
            'map_fields': self._map_fields,
            'format_date': self._format_date,
            'format_currency': self._format_currency,
            'concatenate': self._concatenate,
            'split_string': self._split_string,
            'lookup_value': self._lookup_value,
            'conditional': self._conditional_transform,
            'calculate': self._calculate,
            'validate': self._validate_data
        }
    
    , transformation_rules: List[Dict]) -> Dict:
        """Apply transformation rules to data"""
        try:
            transformed_data = data.copy()
            
            for rule in transformation_rules:
                transformation_type = rule.get('type')
                
                if transformation_type in self.transformers:
                    transformer = self.transformers[transformation_type]
                    transformed_data = transformer(transformed_data, rule)
                else:
                    logger.warning(f"Unknown transformation type: {transformation_type}")
            
            return transformed_data
            
        except Exception as e:
            logger.error(f"Data transformation failed: {e}", exc_info=True)
            raise IntegrationException(f"Data transformation failed: {str(e)}")
    
    def _map_
        """Map fields from source to destination format"""
        field_mappings = rule.get('mappings', {})
        transformed = data.copy()
        
        for source_field, dest_field in field_mappings.items():
            if source_fiel nested field access
                value = self._get_nested_value(data, source_field)
                self._set_nested_value(transformed, dest_field, value)
                
                # Remove original field if different
                if source_field != dest_field and source_field in transformed:
                    del transformed[source_field]
        
        return, rule: Dict) -> Dict:
        """Format date fields"""
        field = rule.get('field')
        input_format = rule.get('input_format', 'auto')
        output_format = rule.get('output_format', '%Y-%m-%d')
        
        if field in data and data[field]:
            try:
                if input_format == 'auto':
                    # Try to parse automatically
                    from dateutil import parser
                    parsed_date = parser.parse(str(data[field]))
                else:
                    parsed_date = datetime.strptime(str(data[field]), input_format)
                
                data[field] = parsed_date.strftime(output_format)
            except ValueError as e:
                logger.warning(f"Date formatting failed for field {field}: {e}")
        
        return data
    
    , rule: Dict) -> Dict:
        """Apply conditional transformations"""
        field = rule.get('field')
        conditions = rule.get('conditions', [
            field_value = data[field]
            
            for condition in conditions:
                if self._evaluate_condition(field_value, condition):
                    transformation = condition.get('transformation', {})
                    if transformation:
                        data = self.transform_data(data, [transformation])
                    break
        
        return data


class SyncEngine:
    """Advanced data synchronization engine"""
    
    def __init__(self, tenant, integration):
        self.tenant = tenant
        self.integration = integration
        self.transformer = DataTransformer(tenant)
    
    def sync_data(self, sync_config: Dict) -> Dict:
        """Execute data synchronization"""
        try:
            sync_type = sync_config.get('type', 'bidirectional')
            
            results = {
                'sync_type': sync_type,
                'started_at': timezone.now().isoformat(),
                'records_processed': 0,
                'records_synced': 0,
                'errors': [],
                'warnings': []
            }
            
            if sync_type in ['inbound', 'bidirectional']:
                inbound_results = self._sync_inbound_data(sync_config)
                results.update({
                    'inbound_processed': inbound_results.get('processed', 0),
                    'inbound_synced': inbound_results.get('synced', 0),
                    'inbound_errors': inbound_results.get('errors', [])
                })
            
            if sync_type in ['outbound', 'bidirectional']:
                outbound_results = self._sync_outbound_data(sync_config)
                results.update({
                    'outbound_processed': outbound_results.get('processed', 0),
                    'outbound_synced': outbound_results.get('synced', 0),
                    'outbound_errors': outbound_results.get('errors', [])
                })
            
            results['completed_at'] = timezone.now().isoformat()
            results['success_rate'] = self._calculate_success_rate(results)
            
            return results
            
        except Exception as e:
            logger.error(f"Data sync failed: {e}", exc_info=True)
            raise IntegrationException(f"Data synchronization failed: {str(e)}")
    
    def _sync_inbound_data(self, sync_config: Dict) -> Dict:
        """Sync data from external system to CRM"""
        results = {'processed': 0, 'synced': 0, 'errors': []}
        
        try:
            # Get data from external system
            connector = APIConnector(self.integration.connection_config)
            
            endpoint = sync_config.get('inbound_endpoint')
            if not endpoint:
                return results
            
            # Fetch data
            external_data = connector.make_request('GET', endpoint)
            
            # Handle paginated responses
            records = self._extract_records_from_response(external_data, sync_config)
            
            for record in records:
                results['processed'] += 1
                
                try:
                    # Transform data
                    transformed_record = self.transformer.transform_data(
                        record, sync_config.get('inbound_transformations', [])
                    )
                    
                    # Create or update CRM record
                    crm_record = self._create_or_update_crm_record(
                        transformed_record, sync_config
                    )
                    
                    if crm_record:
                        results['synced'] += 1
                        
                        # Log successful sync
                        self._log_sync_record(
                            'inbound', 'success', 
                            external_id=record.get('id'),
                            crm_id=crm_record.id,
                            data=transformed_record
                        )
                
                except Exception as e:
                    results['errors'].append({
                        'record_id': record.get('id'),
                        'error': str(e)
                    })
                    
                    self._log_sync_record(
                        'inbound', 'error',
                        external_id=record.get('id'),
                        error=str(e),
                        data=record
                    )
            
            return results
            
        except Exception as e:
            logger.error(f"Inbound sync failed: {e}", exc_info=True)
            results['errors'].append({'general_error': str(e)})
            return results


class WebhookProcessor:
    """Advanced webhook processing system"""
    
    def __init__(self, tenant):
        self.tenant = tenant
        self.processors = {
            'lead_created': self._process_lead_webhook,
            'lead_updated': self._process_lead_webhook,
            'opportunity_created': self._process_opportunity_webhook,
            'opportunity_updated': self._process_opportunity_webhook,
            'contact_created': self._process_contact_webhook,
            'payment_received': self._process_payment_webhook,
            'form_submitted': self._process_form_webhook
        }
    
    def process integration: 'Integration') -> Dict:
        """Process incoming webhook data"""
        try:
            # Validate webhook signature
            if not self._validate_webhook_signature(webhook_data, integration):
                raise IntegrationException(
                    "Invalid webhook signature",
                    code='WEBHOOK_SIGNATURE_INVALID'
                )
            
            event_type = webhook_data.get('event_type') or self._detect_event_type(webhook_data)
            
            if event_type in self.processors:
                processor = self.processors[event_type]
                result = processor(webhook_data, integration)
            else:
                result = self._process_generic_webhook(webhook_data, integration)
            
            # Log successful processing
            self._log_webhook_processing(webhook_data, integration, result, 'success')
            
            return result
            
        except Exception as e:
            logger.error(f"Webhook processing failed: {e}", exc_info=True)
            self._log_webhook_processing(webhook_data, integration, {}, 'error', str(e))
            raise IntegrationException(f"Webhook processing failed: {str(e)}")
    
    def _validate_webhook_signature(self, webhook'Integration') -> bool:
        """Validate webhook signature for security"""
        signature_config = integration.webhook_config.get('signature_validation', {})
        
        if not signature_config.get('enabled', False):
            return True  # Skip validation if not configured
        
        signature_header = signature_config.get('header', 'X-Signature')
        secret = signature_config.get('secret', '')
        
        received_signature = webhook_data.get('headers', {}).get(signature_header, '')
        
        if not received_signature or not secret:
            return False
        
        # Calculate expected signature
        payload = json.dumps(webhook_data.get('payload', {}), sort_keys=True)
        expected_signature = hmac.new(
            secret.encode('utf-8'),
            payload.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        return hmac.compare_digest(received_signature, expected_signature)
    
    def _process_lead_webhook(self, webhook_data: Dict, integration: 'Integration') -> Dict:
        """Process lead-related webhook"""
        from .lead_service import LeadService
        
        payload = webhook_data.get('payload', {})
        event_type = webhook_data.get('event_type')
        
        # Transform webhook data to CRM format
        transformer = DataTransformer(self.tenant)
        lead_data = transformer.transform_data(
            payload,
            integration.webhook_config.get('lead_transformations', [])
        )
        
        lead_service = LeadService(tenant=self.tenant, user=None)
        
        if event_type == 'lead_created':
            lead = lead_service.create_lead(lead_data)
            return {'action': 'created', 'lead_id': lead.id}
        
        elif event_type == 'lead_updated':
            external_id = payload.get('id')
            # Find existing lead by external ID
            lead = self._find_lead_by_external_id(external_id, integration)
            if lead:
                updated_lead = lead_service.update_lead(lead.id, lead_data)
                return {'action': 'updated', 'lead_id': updated_lead.id}
        
        return {'action': 'processed', 'result': 'no_action_taken'}


class IntegrationService(BaseService):
    """Comprehensive integration management service"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.transformer = DataTransformer(self.tenant)
        self.webhook_processor = WebhookProcessor(self.tenant)
    
    # ============================================================================
    # INTEGRATION MANAGEMENT
    # ============================================================================
    
    @transaction.atomic
    def create_integration) -> Integration:
        """
        Create new integration with external system
        
        Args:
        
        Returns:
            Integration instance
        """
        self.context.operation = 'create_integration'
        
        try:
            self.validate_user_permission('crm.add_integration')
            
            # Validate required fields
            required_fields = ['name', 'integration_type', 'connection_config']
            is_valid, errors = self.validate_data(integration_data, {
                field: {'required': True} for field in required_fields
            })
            
            if not is_valid:
                raise IntegrationException(f"Validation failed: {', '.join(errors)}")
            
            # Test connection
            connection_test = self._test_integration_connection(integration_data['connection_config'])
            
            if not connection_test['success']:
                raise IntegrationException(
                    f"Connection test failed: {connection_test.get('error', 'Unknown error')}"
                )
            
            # Create integration
            integration = Integration.objects.create(
                tenant=self.tenant,
                name=integration_data['name'],
                description=integration_data.get('description', ''),
                integration_type=integration_data['integration_type'],
                connection_config=integration_data['connection_config'],
                sync_config=integration_data.get('sync_config', {}),
                webhook_config=integration_data.get('webhook_config', {}),
                is_active=integration_data.get('is_active', True),
                sync_frequency=integration_data.get('sync_frequency', 'HOURLY'),
                created_by=self.user,
                metadata={
                    'connection_test': connection_test,
                    'creation_source': 'manual',
                    'supported_operations': integration_data.get('supported_operations', [])
                }
            )
            
            # Create initial sync mappings
            if integration_data.get('field_mappings'):
                self._create_field_mappings(integration, integration_data['field_mappings'])
            
            # Set up webhooks if configured
            if integration_data.get('webhook_config', {}).get('enabled'):
                self._setup_webhook_endpoints(integration)
            
            # Create API keys if needed
            if integration_data.get('generate_api_key'):
                api_key = self._generate_integration_api_key(integration)
                integration.metadata['api_key_id'] = api_key.id
                integration.save()
            
            self.log_activity(
                'integration_created',
                'Integration',
                integration.id,
                {
                    'name': integration.name,
                    'type': integration.integration_type,
                    'connection_successful': connection_test['success'],
                    'webhook_enabled': integration_data.get('webhook_config', {}).get('enabled', False)
                }
            )
            
            return integration
            
        except Exception as e:
            logger.error(f"Integration creation failed: {e}", exc_info=True)
            raise IntegrationException(f"Integration creation failed: {str(e)}")
    
    def execute_data_sync(self, integration_id: int, sync_type: str = 'bidirectional',
                         force_full_sync: bool = False) -> Dict:
        """
        Execute data synchronization for integration
        
        Args:
            integration_id: Integration ID
            sync_type: Type of sync ('inbound', 'outbound', 'bidirectional')
            force_full_sync: Force full sync instead of incremental
        
        Returns:
            Sync execution results
        """
        try:
            integration = Integration.objects.get(id=integration_id, tenant=self.tenant)
            self.validate_user_permission('crm.change_integration', integration)
            
            if not integration.is_active:
                raise IntegrationException("Integration is not active")
            
            # Create sync job
            sync_job = SyncJob.objects.create(
                integration=integration,
                sync_type=sync_type,
                status='RUNNING',
                started_at=timezone.now(),
                is_full_sync=force_full_sync,
                tenant=self.tenant,
                initiated_by=self.user
            )
            
            try:
                # Execute sync
                sync_engine = SyncEngine(self.tenant, integration)
                
                sync_config = {
                    **integration.sync_config,
                    'type': sync_type,
                    'full_sync': force_full_sync,
                    'last_sync_timestamp': integration.last_sync_at.isoformat() if integration.last_sync_at else None
                }
                
                sync_results = sync_engine.sync_data(sync_config)
                
                # Update sync job
                sync_job.status = 'COMPLETED'
                sync_job.completed_at = timezone.now()
                sync_job.results = sync_results
                sync_job.records_processed = sync_results.get('records_processed', 0)
                sync_job.records_synced = sync_results.get('records_synced', 0)
                sync_job.save()
                
                # Update integration last sync
                integration.last_sync_at = timezone.now()
                integration.save()
                
                self.log_activity(
                    'data_sync_executed',
                    'Integration',
                    integration.id,
                    {
                        'sync_type': sync_type,
                        'records_processed': sync_results.get('records_processed', 0),
                        'records_synced': sync_results.get('records_synced', 0),
                        'success_rate': sync_results.get('success_rate', 0)
                    }
                )
                
                return {
                    'sync_job_id': sync_job.id,
                    'integration_name': integration.name,
                    **sync_results
                }
                
            except Exception as e:
                # Update sync job on failure
                sync_job.status = 'FAILED'
                sync_job.completed_at = timezone.now()
                sync_job.error_message = str(e)
                sync_job.save()
                raise
                
        except Integration.DoesNotExist:
            raise IntegrationException("Integration not found")
        except Exception as e:
            logger.error(f"Data sync execution failed: {e}", exc_info=True)
            raise IntegrationException(f"Data sync execution failed: {str(e)}")
    
    # ============================================================================
    # WEBHOOK MANAGEMENT
    # ============================================================================
    
    def process_incoming_webhook(self, integration"""
        Process incoming webhook from external system
        
        Args: payload and metadata
        
        Returns:
            Processing results
        """
        try:
            integration = Integration.objects.get(id=integration_id, tenant=self.tenant)
            
            if not integration.is_active:
                raise IntegrationException("Integration is not active")
            
            # Process webhook
            processing_results = self.webhook_processor.process_webhook(webhook_data, integration)
            
            # Update integration statistics
            self._update_integration_stats(integration, 'webhook_processed')
            
            return {
                'integration_id': integration.id,
                'integration_name': integration.name,
                'processed_at': timezone.now().isoformat(),
                'processing_results': processing_results
            }
            
        except Integration.DoesNotExist:
            raise IntegrationException("Integration not found")
        except Exception as e:
            logger.error(f"Webhook processing failed: {e}", exc_info=True)
            raise IntegrationException(f"Webhook processing failed: {str(e)}")
    
    def create_outbound_webhook(self, integration_id: int, event_type: str, 
                              target_url: str, data: Dict) -> Dict:
        """
        Send outbound webhook to external system
        
        Args:
            integration_id: Integration ID
            event_type: Type of event
            target_url: Webhook URL
            Webhook delivery results
        """
        try:
            integration = Integration.objects.get(id=integration_id, tenant=self.tenant)
            
            # Transform data for external system
            transformed_data = self.transformer.transform_data(
                data,
                integration.webhook_config.get('outbound_transformations', [])
            )
            
            # Prepare webhook payload
            webhook_payload = {
                'event_type': event_type,
                'timestamp': timezone.now().isoformat(),
                'tenant_id': str(self.tenant.id),
                'data': transformed_data
            }
            
            # Add signature if configured
            if integration.webhook_config.get('signature', {}).get('enabled'):
                signature = self._generate_webhook_signature(
                    webhook_payload,
                    integration.webhook_config['signature']['secret']
                )
                headers = {'X-Signature': signature}
            else:
                headers = {}
            
            # Send webhook
            connector = APIConnector(integration.connection_config)
            response = connector.make_request(
                'POST',
                target_url,
                data=webhook_payload,
                headers=headers
            )
            
            # Log webhook delivery
            self._log_webhook_delivery(
                integration, event_type, target_url, 
                webhook_payload, response, 'success'
            )
            
            return {
                'delivered': True,
                'response_status': response.get('status_code', 200),
                'delivered_at': timezone.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Outbound webhook failed: {e}", exc_info=True)
            
            # Log failed delivery
            self._log_webhook_delivery(
                integration, event_type, target_url,
                data, {}, 'error', str(e)
            )
            
            raise IntegrationException(f"Webhook delivery failed: {str(e)}")
    
    # ============================================================================
    # INTEGRATION ANALYTICS AND MONITORING
    # ============================================================================
    
    def get_integration_health_dashboard(self, integration_id: int = None) -> Dict:
        """
        Get comprehensive integration health dashboard
        
        Args:
            integration_id: Specific integration (all integrations if None)
        
        Returns:
            Integration health dashboard data
        """
        try:
            # Build query
            integrations_query = Integration.objects.filter(tenant=self.tenant)
            if integration_id:
                integrations_query = integrations_query.filter(id=integration_id)
            
            dashboard_data = {
                'generated_at': timezone.now().isoformat(),
                'scope': 'single' if integration_id else 'all',
                'integrations': []
            }
            
            for integration in integrations_query:
                integration_health = {
                    'integration_id': integration.id,
                    'name': integration.name,
                    'type': integration.integration_type,
                    'is_active': integration.is_active,
                    'last_sync': integration.last_sync_at.isoformat() if integration.last_sync_at else None,
                    'health_score': self._calculate_integration_health_score(integration),
                    'sync_statistics': self._get_sync_statistics(integration),
                    'webhook_statistics': self._get_webhook_statistics(integration),
                    'error_analysis': self._get_error_analysis(integration),
                    'performance_metrics': self._get_performance_metrics(integration)
                }
                
                dashboard_data['integrations'].append(integration_health)
            
            # Overall summary
            if not integration_id:
                dashboard_data['summary'] = self._generate_integrations_summary(
                    dashboard_data['integrations']
                )
            
            return dashboard_data
            
        except Exception as e:
            logger.error(f"Integration health dashboard failed: {e}", exc_info=True)
            raise IntegrationException(f"Health dashboard generation failed: {str(e)}")
    
    # ============================================================================
    # HELPER METHODS
    # ============================================================================
    
    def _test_integration_connection(self, connection_config: Dict) -> Dict:
        """Test integration connection"""
        try:
            connector = APIConnector(connection_config)
            
            # Use test endpoint if specified
            test_endpoint = connection_config.get('test_endpoint', '/health')
            
            response = connector.make_request('GET', test_endpoint)
            
            return {
                'success': True,
                'response_time': 200,  # Would be measured
                'status_code': response.get('status_code', 200),
                'tested_at': timezone.now().isoformat()
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'tested_at': timezone.now().isoformat()
            }
    
    def _calculate_integration_health_score(self, integration: Integration) -> int:
        """Calculate integration health score (0-100)"""
        score = 100
        
        # Check if active
        if not integration.is_active:
            score -= 50
        
        # Check last sync time
        if integration.last_sync_at:
            days_since_sync = (timezone.now() - integration.last_sync_at).days
            if days_since_sync > 7:
                score -= 30
            elif days_since_sync > 3:
                score -= 15
        else:
            score -= 25  # Never synced
        
        # Check recent errors
        recent_errors = IntegrationError.objects.filter(
            integration=integration,
            created_at__gte=timezone.now() - timedelta(days=7)
        ).count()
        
        if recent_errors > 10:
            score -= 20
        elif recent_errors > 5:
            score -= 10
        
        return max(0, score)
    
    def _generate_webhook_signature(self, payload: Dict, secret: str) -> str:
        """Generate webhook signature for outbound webhooks"""
        payload_string = json.dumps(payload, sort_keys=True)
        signature = hmac.new(
            secret.encode('utf-8'),
            payload_string.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        return signature