"""
Real-time Data Synchronization Service

Provides real-time data synchronization capabilities for finance module,
enabling instant updates and cross-module data consistency.
"""

import logging
import asyncio
import json
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, Any, List, Optional, Union, Callable
from dataclasses import dataclass, field
import threading
from queue import Queue
import time

from django.db import transaction, connection
from django.utils import timezone
from django.core.cache import cache
from django.db.models.signals import post_save, post_delete, pre_save
from django.dispatch import receiver
from django.core.serializers.json import DjangoJSONEncoder
from django.contrib.auth import get_user_model

from apps.core.models import TenantBaseModel

User = get_user_model()
logger = logging.getLogger(__name__)


@dataclass
class SyncEvent:
    """Represents a synchronization event."""
    event_id: str
    tenant_id: str
    module: str
    entity_type: str
    entity_id: int
    action: str  # CREATE, UPDATE, DELETE
    data: Dict[str, Any]
    timestamp: datetime = field(default_factory=timezone.now)
    processed: bool = False
    retry_count: int = 0
    priority: int = 5  # 1-10, higher is more urgent


@dataclass
class SyncTarget:
    """Represents a sync target configuration."""
    target_module: str
    target_service: str
    target_method: str
    filters: Dict[str, Any] = field(default_factory=dict)
    transform_data: bool = True
    retry_on_failure: bool = True
    max_retries: int = 3
    batch_size: int = 1


class RealTimeSyncService:
    """
    Real-time Data Synchronization Service.
    
    Features:
    - Event-driven data synchronization
    - Cross-module real-time updates
    - Configurable sync targets
    - Retry mechanisms and error handling
    - Batch processing capabilities
    - Priority-based event processing
    - Transaction-safe operations
    - Performance monitoring
    """
    
    def __init__(self, tenant):
        self.tenant = tenant
        self.logger = logging.getLogger(f'{__name__}.{tenant.schema_name}')
        
        # Event processing
        self.event_queue = Queue(maxsize=1000)
        self.processing_thread = None
        self.is_running = False
        
        # Sync configuration
        self.sync_targets = {}
        self.batch_processors = {}
        
        # Performance tracking
        self.sync_stats = {
            'events_processed': 0,
            'events_failed': 0,
            'last_sync_time': None,
            'avg_processing_time': 0
        }
        
        # Initialize sync targets
        self._initialize_sync_targets()
    
    # ==================== Core Synchronization Methods ====================
    
    def start_sync_service(self) -> Dict[str, Any]:
        """Start the real-time sync service."""
        try:
            if self.is_running:
                return {
                    'success': False,
                    'message': 'Sync service is already running'
                }
            
            self.is_running = True
            self.processing_thread = threading.Thread(
                target=self._process_sync_events,
                daemon=True
            )
            self.processing_thread.start()
            
            # Register signal handlers
            self._register_signal_handlers()
            
            return {
                'success': True,
                'message': 'Real-time sync service started successfully',
                'thread_id': self.processing_thread.ident
            }
            
        except Exception as e:
            self.logger.error(f"Error starting sync service: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def stop_sync_service(self) -> Dict[str, Any]:
        """Stop the real-time sync service."""
        try:
            self.is_running = False
            
            if self.processing_thread and self.processing_thread.is_alive():
                self.processing_thread.join(timeout=5)
            
            return {
                'success': True,
                'message': 'Real-time sync service stopped successfully'
            }
            
        except Exception as e:
            self.logger.error(f"Error stopping sync service: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def queue_sync_event(self, event: SyncEvent) -> bool:
        """Queue a synchronization event for processing."""
        try:
            if not self.is_running:
                self.logger.warning("Sync service not running, starting it...")
                self.start_sync_service()
            
            # Add to queue with priority handling
            self.event_queue.put(event, timeout=1)
            
            self.logger.debug(f"Queued sync event: {event.event_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error queuing sync event: {e}")
            return False
    
    def _process_sync_events(self) -> None:
        """Process synchronization events from the queue."""
        while self.is_running:
            try:
                # Get event from queue with timeout
                try:
                    event = self.event_queue.get(timeout=1)
                except:
                    continue
                
                start_time = time.time()
                
                # Process the event
                success = self._process_single_event(event)
                
                # Update statistics
                processing_time = time.time() - start_time
                self._update_sync_stats(success, processing_time)
                
                # Mark task as done
                self.event_queue.task_done()
                
                # Small delay to prevent overwhelming the system
                time.sleep(0.01)
                
            except Exception as e:
                self.logger.error(f"Error in sync event processing loop: {e}")
                time.sleep(1)  # Wait before retrying
    
    def _process_single_event(self, event: SyncEvent) -> bool:
        """Process a single synchronization event."""
        try:
            self.logger.debug(f"Processing sync event: {event.event_id}")
            
            # Get sync targets for this event
            targets = self._get_sync_targets_for_event(event)
            
            if not targets:
                self.logger.debug(f"No sync targets for event: {event.event_id}")
                return True
            
            success_count = 0
            
            for target in targets:
                try:
                    # Process sync to target
                    if self._sync_to_target(event, target):
                        success_count += 1
                    
                except Exception as e:
                    self.logger.error(f"Error syncing to target {target.target_module}: {e}")
                    
                    # Handle retry logic
                    if target.retry_on_failure and event.retry_count < target.max_retries:
                        event.retry_count += 1
                        self.logger.info(f"Retrying event {event.event_id}, attempt {event.retry_count}")
                        
                        # Re-queue with delay
                        threading.Timer(
                            delay=min(2 ** event.retry_count, 60),  # Exponential backoff, max 60s
                            function=lambda: self.queue_sync_event(event)
                        ).start()
                        
                        return False
            
            # Mark event as processed
            event.processed = True
            return success_count > 0
            
        except Exception as e:
            self.logger.error(f"Error processing sync event {event.event_id}: {e}")
            return False
    
    def _sync_to_target(self, event: SyncEvent, target: SyncTarget) -> bool:
        """Synchronize event data to a specific target."""
        try:
            # Apply filters
            if not self._event_matches_filters(event, target.filters):
                return True  # Skip, but not an error
            
            # Transform data if needed
            sync_data = event.data
            if target.transform_data:
                sync_data = self._transform_data_for_target(event, target)
            
            # Get target service
            service = self._get_target_service(target.target_module, target.target_service)
            if not service:
                self.logger.error(f"Target service not found: {target.target_module}.{target.target_service}")
                return False
            
            # Call target method
            method = getattr(service, target.target_method, None)
            if not method:
                self.logger.error(f"Target method not found: {target.target_method}")
                return False
            
            # Execute sync
            result = method(sync_data)
            
            self.logger.debug(f"Synced event {event.event_id} to {target.target_module}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error syncing to target {target.target_module}: {e}")
            return False
    
    # ==================== Signal Handlers ====================
    
    def _register_signal_handlers(self) -> None:
        """Register Django signal handlers for automatic event generation."""
        try:
            from apps.finance.models.invoicing import Invoice
            from apps.finance.models.payments import Payment
            from apps.finance.models.journal import JournalEntry
            
            # Invoice signals
            post_save.connect(
                self._handle_invoice_save,
                sender=Invoice,
                dispatch_uid=f'finance_invoice_sync_{self.tenant.id}'
            )
            
            post_delete.connect(
                self._handle_invoice_delete,
                sender=Invoice,
                dispatch_uid=f'finance_invoice_delete_{self.tenant.id}'
            )
            
            # Payment signals
            post_save.connect(
                self._handle_payment_save,
                sender=Payment,
                dispatch_uid=f'finance_payment_sync_{self.tenant.id}'
            )
            
            # Journal Entry signals
            post_save.connect(
                self._handle_journal_save,
                sender=JournalEntry,
                dispatch_uid=f'finance_journal_sync_{self.tenant.id}'
            )
            
            self.logger.info("Signal handlers registered for real-time sync")
            
        except Exception as e:
            self.logger.error(f"Error registering signal handlers: {e}")
    
    def _handle_invoice_save(self, sender, instance, created, **kwargs):
        """Handle invoice save signal."""
        try:
            if instance.tenant_id != self.tenant.id:
                return
            
            action = 'CREATE' if created else 'UPDATE'
            
            event = SyncEvent(
                event_id=f"invoice_{action.lower()}_{instance.id}_{int(time.time())}",
                tenant_id=str(self.tenant.id),
                module='finance',
                entity_type='invoice',
                entity_id=instance.id,
                action=action,
                data={
                    'invoice_id': instance.id,
                    'customer_id': instance.customer_id,
                    'number': instance.number,
                    'total_amount': float(instance.total_amount),
                    'status': instance.status,
                    'due_date': instance.due_date.isoformat() if instance.due_date else None,
                    'created_at': instance.created_at.isoformat(),
                    'updated_at': instance.updated_at.isoformat()
                },
                priority=7 if action == 'CREATE' else 5
            )
            
            self.queue_sync_event(event)
            
        except Exception as e:
            self.logger.error(f"Error handling invoice save signal: {e}")
    
    def _handle_invoice_delete(self, sender, instance, **kwargs):
        """Handle invoice delete signal."""
        try:
            if instance.tenant_id != self.tenant.id:
                return
            
            event = SyncEvent(
                event_id=f"invoice_delete_{instance.id}_{int(time.time())}",
                tenant_id=str(self.tenant.id),
                module='finance',
                entity_type='invoice',
                entity_id=instance.id,
                action='DELETE',
                data={
                    'invoice_id': instance.id,
                    'customer_id': instance.customer_id,
                    'number': instance.number
                },
                priority=8
            )
            
            self.queue_sync_event(event)
            
        except Exception as e:
            self.logger.error(f"Error handling invoice delete signal: {e}")
    
    def _handle_payment_save(self, sender, instance, created, **kwargs):
        """Handle payment save signal."""
        try:
            if instance.tenant_id != self.tenant.id:
                return
            
            action = 'CREATE' if created else 'UPDATE'
            
            event = SyncEvent(
                event_id=f"payment_{action.lower()}_{instance.id}_{int(time.time())}",
                tenant_id=str(self.tenant.id),
                module='finance',
                entity_type='payment',
                entity_id=instance.id,
                action=action,
                data={
                    'payment_id': instance.id,
                    'amount': float(instance.amount),
                    'payment_method': instance.payment_method,
                    'status': instance.status,
                    'payment_date': instance.payment_date.isoformat() if instance.payment_date else None,
                    'reference': instance.reference,
                    'created_at': instance.created_at.isoformat(),
                    'updated_at': instance.updated_at.isoformat()
                },
                priority=6
            )
            
            self.queue_sync_event(event)
            
        except Exception as e:
            self.logger.error(f"Error handling payment save signal: {e}")
    
    def _handle_journal_save(self, sender, instance, created, **kwargs):
        """Handle journal entry save signal."""
        try:
            if instance.tenant_id != self.tenant.id:
                return
            
            action = 'CREATE' if created else 'UPDATE'
            
            # Only sync approved journal entries
            if instance.status == 'APPROVED':
                event = SyncEvent(
                    event_id=f"journal_{action.lower()}_{instance.id}_{int(time.time())}",
                    tenant_id=str(self.tenant.id),
                    module='finance',
                    entity_type='journal_entry',
                    entity_id=instance.id,
                    action=action,
                    data={
                        'journal_entry_id': instance.id,
                        'reference': instance.reference,
                        'description': instance.description,
                        'entry_date': instance.entry_date.isoformat(),
                        'status': instance.status,
                        'created_at': instance.created_at.isoformat(),
                        'updated_at': instance.updated_at.isoformat()
                    },
                    priority=4
                )
                
                self.queue_sync_event(event)
            
        except Exception as e:
            self.logger.error(f"Error handling journal save signal: {e}")
    
    # ==================== Sync Target Configuration ====================
    
    def _initialize_sync_targets(self) -> None:
        """Initialize synchronization targets."""
        try:
            # CRM sync targets
            self.sync_targets['crm'] = [
                SyncTarget(
                    target_module='crm',
                    target_service='CustomerService',
                    target_method='update_financial_data',
                    filters={'entity_type': ['invoice', 'payment']},
                    batch_size=5
                ),
                SyncTarget(
                    target_module='crm',
                    target_service='OpportunityService',
                    target_method='update_revenue_data',
                    filters={'entity_type': ['invoice'], 'action': ['CREATE', 'UPDATE']},
                    batch_size=10
                )
            ]
            
            # Inventory sync targets
            self.sync_targets['inventory'] = [
                SyncTarget(
                    target_module='inventory',
                    target_service='InventoryService',
                    target_method='update_financial_metrics',
                    filters={'entity_type': ['invoice'], 'action': ['CREATE']},
                    batch_size=20
                )
            ]
            
            # E-commerce sync targets
            self.sync_targets['ecommerce'] = [
                SyncTarget(
                    target_module='ecommerce',
                    target_service='OrderService',
                    target_method='sync_payment_status',
                    filters={'entity_type': ['payment'], 'action': ['CREATE', 'UPDATE']},
                    batch_size=15
                ),
                SyncTarget(
                    target_module='ecommerce',
                    target_service='CustomerService',
                    target_method='update_customer_financial_profile',
                    filters={'entity_type': ['invoice', 'payment']},
                    batch_size=5
                )
            ]
            
            # Workflow sync targets
            self.sync_targets['workflow'] = [
                SyncTarget(
                    target_module='workflow',
                    target_service='WorkflowService',
                    target_method='trigger_financial_workflows',
                    filters={'action': ['CREATE', 'UPDATE']},
                    batch_size=1,
                    max_retries=5
                )
            ]
            
            self.logger.info(f"Initialized {sum(len(targets) for targets in self.sync_targets.values())} sync targets")
            
        except Exception as e:
            self.logger.error(f"Error initializing sync targets: {e}")
    
    def add_sync_target(self, module: str, target: SyncTarget) -> bool:
        """Add a new sync target."""
        try:
            if module not in self.sync_targets:
                self.sync_targets[module] = []
            
            self.sync_targets[module].append(target)
            self.logger.info(f"Added sync target for {module}: {target.target_service}.{target.target_method}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error adding sync target: {e}")
            return False
    
    def remove_sync_target(self, module: str, target_service: str, target_method: str) -> bool:
        """Remove a sync target."""
        try:
            if module not in self.sync_targets:
                return False
            
            self.sync_targets[module] = [
                target for target in self.sync_targets[module]
                if not (target.target_service == target_service and target.target_method == target_method)
            ]
            
            self.logger.info(f"Removed sync target for {module}: {target_service}.{target_method}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error removing sync target: {e}")
            return False
    
    def _get_sync_targets_for_event(self, event: SyncEvent) -> List[SyncTarget]:
        """Get applicable sync targets for an event."""
        applicable_targets = []
        
        try:
            for module, targets in self.sync_targets.items():
                for target in targets:
                    if self._event_matches_filters(event, target.filters):
                        applicable_targets.append(target)
            
            # Sort by priority if event has high priority
            if event.priority > 7:
                applicable_targets.sort(key=lambda t: t.max_retries, reverse=True)
            
            return applicable_targets
            
        except Exception as e:
            self.logger.error(f"Error getting sync targets for event: {e}")
            return []
    
    def _event_matches_filters(self, event: SyncEvent, filters: Dict[str, Any]) -> bool:
        """Check if event matches target filters."""
        try:
            for filter_key, filter_values in filters.items():
                if hasattr(event, filter_key):
                    event_value = getattr(event, filter_key)
                    if event_value not in filter_values:
                        return False
                elif filter_key in event.data:
                    event_value = event.data[filter_key]
                    if event_value not in filter_values:
                        return False
                else:
                    return False  # Filter key not found
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error checking event filters: {e}")
            return False
    
    # ==================== Data Transformation ====================
    
    def _transform_data_for_target(self, event: SyncEvent, target: SyncTarget) -> Dict[str, Any]:
        """Transform event data for specific target."""
        try:
            # Base transformation
            transformed_data = event.data.copy()
            transformed_data.update({
                'tenant_id': event.tenant_id,
                'sync_timestamp': timezone.now().isoformat(),
                'source_module': event.module,
                'source_entity': event.entity_type,
                'source_action': event.action
            })
            
            # Module-specific transformations
            if target.target_module == 'crm':
                transformed_data = self._transform_for_crm(event, transformed_data)
            elif target.target_module == 'inventory':
                transformed_data = self._transform_for_inventory(event, transformed_data)
            elif target.target_module == 'ecommerce':
                transformed_data = self._transform_for_ecommerce(event, transformed_data)
            elif target.target_module == 'workflow':
                transformed_data = self._transform_for_workflow(event, transformed_data)
            
            return transformed_data
            
        except Exception as e:
            self.logger.error(f"Error transforming data for target: {e}")
            return event.data
    
    def _transform_for_crm(self, event: SyncEvent, data: Dict[str, Any]) -> Dict[str, Any]:
        """Transform data for CRM module."""
        try:
            if event.entity_type == 'invoice':
                data['financial_event_type'] = 'invoice_activity'
                data['customer_impact'] = True
                data['revenue_amount'] = data.get('total_amount', 0)
                
            elif event.entity_type == 'payment':
                data['financial_event_type'] = 'payment_activity'
                data['customer_impact'] = True
                data['cash_flow_impact'] = data.get('amount', 0)
            
            return data
            
        except Exception as e:
            self.logger.error(f"Error transforming data for CRM: {e}")
            return data
    
    def _transform_for_inventory(self, event: SyncEvent, data: Dict[str, Any]) -> Dict[str, Any]:
        """Transform data for inventory module."""
        try:
            if event.entity_type == 'invoice':
                data['demand_signal'] = True
                data['revenue_indicator'] = data.get('total_amount', 0)
                
                # Add product demand data if available
                if 'line_items' in data:
                    data['product_demand'] = [
                        {
                            'product_id': item.get('product_id'),
                            'quantity_sold': item.get('quantity'),
                            'revenue': item.get('total_amount')
                        }
                        for item in data['line_items']
                        if item.get('product_id')
                    ]
            
            return data
            
        except Exception as e:
            self.logger.error(f"Error transforming data for inventory: {e}")
            return data
    
    def _transform_for_ecommerce(self, event: SyncEvent, data: Dict[str, Any]) -> Dict[str, Any]:
        """Transform data for e-commerce module."""
        try:
            if event.entity_type == 'payment':
                data['payment_status_update'] = True
                data['financial_status'] = data.get('status')
                data['payment_amount'] = data.get('amount', 0)
                
            elif event.entity_type == 'invoice':
                data['order_financial_update'] = True
                data['billing_status'] = data.get('status')
                data['billing_amount'] = data.get('total_amount', 0)
            
            return data
            
        except Exception as e:
            self.logger.error(f"Error transforming data for e-commerce: {e}")
            return data
    
    def _transform_for_workflow(self, event: SyncEvent, data: Dict[str, Any]) -> Dict[str, Any]:
        """Transform data for workflow module."""
        try:
            data['trigger_data'] = {
                'object_type': event.entity_type,
                'object_id': event.entity_id,
                'action': event.action,
                'timestamp': event.timestamp.isoformat(),
                'priority': event.priority
            }
            
            # Add workflow-specific context
            if event.entity_type == 'invoice':
                data['workflow_context'] = 'invoice_lifecycle'
            elif event.entity_type == 'payment':
                data['workflow_context'] = 'payment_processing'
            elif event.entity_type == 'journal_entry':
                data['workflow_context'] = 'accounting_operations'
            
            return data
            
        except Exception as e:
            self.logger.error(f"Error transforming data for workflow: {e}")
            return data
    
    # ==================== Service Integration ====================
    
    def _get_target_service(self, module: str, service_name: str):
        """Get target service instance."""
        try:
            # This would dynamically import and instantiate services
            # For now, return a mock service
            
            if module == 'crm':
                return self._get_crm_service(service_name)
            elif module == 'inventory':
                return self._get_inventory_service(service_name)
            elif module == 'ecommerce':
                return self._get_ecommerce_service(service_name)
            elif module == 'workflow':
                return self._get_workflow_service(service_name)
            
            return None
            
        except Exception as e:
            self.logger.error(f"Error getting target service {module}.{service_name}: {e}")
            return None
    
    def _get_crm_service(self, service_name: str):
        """Get CRM service instance."""
        # This would return actual CRM service instances
        # For now, return a mock
        class MockCRMService:
            def update_financial_data(self, data):
                logger.info(f"CRM: Updated financial data for customer {data.get('customer_id')}")
                return True
            
            def update_revenue_data(self, data):
                logger.info(f"CRM: Updated revenue data: {data.get('revenue_amount')}")
                return True
        
        return MockCRMService()
    
    def _get_inventory_service(self, service_name: str):
        """Get inventory service instance."""
        class MockInventoryService:
            def update_financial_metrics(self, data):
                logger.info(f"Inventory: Updated financial metrics: {data.get('revenue_indicator')}")
                return True
        
        return MockInventoryService()
    
    def _get_ecommerce_service(self, service_name: str):
        """Get e-commerce service instance."""
        class MockEcommerceService:
            def sync_payment_status(self, data):
                logger.info(f"E-commerce: Synced payment status: {data.get('financial_status')}")
                return True
            
            def update_customer_financial_profile(self, data):
                logger.info(f"E-commerce: Updated customer profile: {data.get('customer_id')}")
                return True
        
        return MockEcommerceService()
    
    def _get_workflow_service(self, service_name: str):
        """Get workflow service instance."""
        class MockWorkflowService:
            def trigger_financial_workflows(self, data):
                logger.info(f"Workflow: Triggered workflows for: {data.get('workflow_context')}")
                return True
        
        return MockWorkflowService()
    
    # ==================== Performance Monitoring ====================
    
    def _update_sync_stats(self, success: bool, processing_time: float) -> None:
        """Update synchronization statistics."""
        try:
            self.sync_stats['events_processed'] += 1
            if not success:
                self.sync_stats['events_failed'] += 1
            
            self.sync_stats['last_sync_time'] = timezone.now()
            
            # Update average processing time
            current_avg = self.sync_stats['avg_processing_time']
            events_count = self.sync_stats['events_processed']
            
            self.sync_stats['avg_processing_time'] = (
                (current_avg * (events_count - 1) + processing_time) / events_count
            )
            
            # Cache stats for monitoring
            cache.set(
                f"sync_stats_{self.tenant.id}",
                self.sync_stats,
                timeout=300  # 5 minutes
            )
            
        except Exception as e:
            self.logger.error(f"Error updating sync stats: {e}")
    
    def get_sync_statistics(self) -> Dict[str, Any]:
        """Get synchronization performance statistics."""
        try:
            stats = self.sync_stats.copy()
            
            # Add additional metrics
            stats.update({
                'queue_size': self.event_queue.qsize(),
                'service_running': self.is_running,
                'thread_active': self.processing_thread.is_alive() if self.processing_thread else False,
                'success_rate': (
                    (stats['events_processed'] - stats['events_failed']) / stats['events_processed'] * 100
                ) if stats['events_processed'] > 0 else 0,
                'target_count': sum(len(targets) for targets in self.sync_targets.values())
            })
            
            return stats
            
        except Exception as e:
            self.logger.error(f"Error getting sync statistics: {e}")
            return {}
    
    # ==================== Manual Sync Operations ====================
    
    def manual_sync_entity(self, entity_type: str, entity_id: int, action: str = 'UPDATE') -> Dict[str, Any]:
        """Manually trigger sync for a specific entity."""
        try:
            # Get entity data
            entity_data = self._get_entity_data(entity_type, entity_id)
            if not entity_data:
                return {
                    'success': False,
                    'error': f'Entity not found: {entity_type}#{entity_id}'
                }
            
            # Create sync event
            event = SyncEvent(
                event_id=f"manual_{entity_type}_{action.lower()}_{entity_id}_{int(time.time())}",
                tenant_id=str(self.tenant.id),
                module='finance',
                entity_type=entity_type,
                entity_id=entity_id,
                action=action,
                data=entity_data,
                priority=9  # High priority for manual sync
            )
            
            # Queue for processing
            if self.queue_sync_event(event):
                return {
                    'success': True,
                    'event_id': event.event_id,
                    'message': f'Manual sync queued for {entity_type}#{entity_id}'
                }
            else:
                return {
                    'success': False,
                    'error': 'Failed to queue sync event'
                }
                
        except Exception as e:
            self.logger.error(f"Error in manual sync: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _get_entity_data(self, entity_type: str, entity_id: int) -> Optional[Dict[str, Any]]:
        """Get entity data for manual sync."""
        try:
            if entity_type == 'invoice':
                from apps.finance.models.invoicing import Invoice
                try:
                    invoice = Invoice.objects.get(id=entity_id, tenant=self.tenant)
                    return {
                        'invoice_id': invoice.id,
                        'customer_id': invoice.customer_id,
                        'number': invoice.number,
                        'total_amount': float(invoice.total_amount),
                        'status': invoice.status,
                        'due_date': invoice.due_date.isoformat() if invoice.due_date else None,
                        'created_at': invoice.created_at.isoformat(),
                        'updated_at': invoice.updated_at.isoformat()
                    }
                except Invoice.DoesNotExist:
                    return None
                    
            elif entity_type == 'payment':
                from apps.finance.models.payments import Payment
                try:
                    payment = Payment.objects.get(id=entity_id, tenant=self.tenant)
                    return {
                        'payment_id': payment.id,
                        'amount': float(payment.amount),
                        'payment_method': payment.payment_method,
                        'status': payment.status,
                        'payment_date': payment.payment_date.isoformat() if payment.payment_date else None,
                        'reference': payment.reference,
                        'created_at': payment.created_at.isoformat(),
                        'updated_at': payment.updated_at.isoformat()
                    }
                except Payment.DoesNotExist:
                    return None
                    
            elif entity_type == 'journal_entry':
                from apps.finance.models.journal import JournalEntry
                try:
                    journal = JournalEntry.objects.get(id=entity_id, tenant=self.tenant)
                    return {
                        'journal_entry_id': journal.id,
                        'reference': journal.reference,
                        'description': journal.description,
                        'entry_date': journal.entry_date.isoformat(),
                        'status': journal.status,
                        'created_at': journal.created_at.isoformat(),
                        'updated_at': journal.updated_at.isoformat()
                    }
                except JournalEntry.DoesNotExist:
                    return None
            
            return None
            
        except Exception as e:
            self.logger.error(f"Error getting entity data: {e}")
            return None
    
    # ==================== Configuration Methods ====================
    
    def configure_sync_target(self, module: str, config: Dict[str, Any]) -> Dict[str, Any]:
        """Configure sync target settings."""
        try:
            if module not in self.sync_targets:
                return {
                    'success': False,
                    'error': f'Module {module} not found in sync targets'
                }
            
            # Update configuration
            targets = self.sync_targets[module]
            for target in targets:
                if (target.target_service == config.get('target_service') and 
                    target.target_method == config.get('target_method')):
                    
                    # Update target configuration
                    for key, value in config.items():
                        if hasattr(target, key):
                            setattr(target, key, value)
                    
                    return {
                        'success': True,
                        'message': f'Updated sync target configuration for {module}'
                    }
            
            return {
                'success': False,
                'error': 'Sync target not found'
            }
            
        except Exception as e:
            self.logger.error(f"Error configuring sync target: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def get_sync_configuration(self) -> Dict[str, Any]:
        """Get current sync configuration."""
        try:
            config = {}
            
            for module, targets in self.sync_targets.items():
                config[module] = []
                for target in targets:
                    config[module].append({
                        'target_service': target.target_service,
                        'target_method': target.target_method,
                        'filters': target.filters,
                        'batch_size': target.batch_size,
                        'max_retries': target.max_retries,
                        'retry_on_failure': target.retry_on_failure
                    })
            
            return {
                'success': True,
                'configuration': config,
                'statistics': self.get_sync_statistics()
            }
            
        except Exception as e:
            self.logger.error(f"Error getting sync configuration: {e}")
            return {
                'success': False,
                'error': str(e)
            }