"""
Event Bus Service
Coordinates event flow and ensures reliable processing
"""

from typing import Dict, Any, List, Optional, Callable
import asyncio
import json
from datetime import datetime
from dataclasses import dataclass, asdict

from ...domain.events.base import DomainEvent
from ...infrastructure.messaging.publishers import EventPublisher
from ...infrastructure.messaging.subscribers import EventSubscriber
from .base import BaseApplicationService


@dataclass
class EventProcessingResult:
    """Result of event processing"""
    event_id: str
    success: bool
    processed_at: datetime
    processing_time_ms: int
    error_message: Optional[str] = None
    retry_count: int = 0


@dataclass
class EventSubscription:
    """Event subscription configuration"""
    event_type: str
    handler: Callable
    max_retries: int = 3
    retry_delay_seconds: int = 5
    dead_letter_enabled: bool = True


class EventBusService(BaseApplicationService):
    """Service for managing event bus operations"""
    
    def __init__(self, tenant):
        super().__init__(tenant)
        self.publisher = EventPublisher(tenant)
        self.subscriber = EventSubscriber(tenant)
        
        # Event processing tracking
        self.processing_results: Dict[str, EventProcessingResult] = {}
        self.failed_events: List[Dict[str, Any]] = []
        
        # Subscriptions registry
        self.subscriptions: Dict[str, EventSubscription] = {}
        
        # Performance metrics
        self.metrics = {
            'events_published': 0,
            'events_processed': 0,
            'events_failed': 0,
            'average_processing_time': 0
        }
    
    def register_handler(self, event_type: str, handler: Callable, 
                        max_retries: int = 3, retry_delay: int = 5):
        """Register event handler with configuration"""
        subscription = EventSubscription(
            event_type=event_type,
            handler=handler,
            max_retries=max_retries,
            retry_delay_seconds=retry_delay
        )
        
        self.subscriptions[event_type] = subscription
        self.subscriber.subscribe(event_type, self._process_event_with_retry)
        
        self.log_info(f"Registered handler for event type: {event_type}")
    
    async def publish_event(self, event: DomainEvent, ensure_delivery: bool = True) -> bool:
        """Publish event with delivery guarantees"""
        try:
            start_time = datetime.now()
            
            # Publish event
            success = await self.publisher.publish_async(event)
            
            if success:
                self.metrics['events_published'] += 1
                
                if ensure_delivery:
                    # Wait for acknowledgment
                    await self._wait_for_processing_confirmation(event.event_id)
                
                processing_time = (datetime.now() - start_time).total_seconds() * 1000
                self.log_info(f"Event published successfully: {event.event_type}", {
                    'event_id': event.event_id,
                    'processing_time_ms': processing_time
                })
                
                return True
            else:
                self.log_error(f"Failed to publish event: {event.event_type}")
                return False
                
        except Exception as e:
            self.log_error("Event publishing failed", e)
            return False
    
    async def publish_events_batch(self, events: List[DomainEvent]) -> Dict[str, bool]:
        """Publish multiple events in batch"""
        results = {}
        
        # Group events by type for optimization
        events_by_type = {}
        for event in events:
            if event.event_type not in events_by_type:
                events_by_type[event.event_type] = []
            events_by_type[event.event_type].append(event)
        
        # Publish each group
        for event_type, type_events in events_by_type.items():
            try:
                batch_results = await self.publisher.publish_batch_async(type_events)
                results.update(batch_results)
                
                successful_count = sum(1 for success in batch_results.values() if success)
                self.metrics['events_published'] += successful_count
                
                self.log_info(f"Published batch of {len(type_events)} {event_type} events", {
                    'successful': successful_count,
                    'failed': len(type_events) - successful_count
                })
                
            except Exception as e:
                self.log_error(f"Batch publishing failed for {event_type}", e)
                for event in type_events:
                    results[event.event_id] = False
        
        return results
    
    async def _process_event_with_retry(self, event_data: Dict[str, Any]):
        """Process event with retry logic"""
        event_id = event_data.get('event_id', 'unknown')
        event_type = event_data.get('event_type', 'unknown')
        
        start_time = datetime.now()
        retry_count = 0
        
        subscription = self.subscriptions.get(event_type)
        if not subscription:
            self.log_error(f"No subscription found for event type: {event_type}")
            return
        
        while retry_count <= subscription.max_retries:
            try:
                # Process event
                await subscription.handler(event_data)
                
                # Record successful processing
                processing_time = (datetime.now() - start_time).total_seconds() * 1000
                result = EventProcessingResult(
                    event_id=event_id,
                    success=True,
                    processed_at=datetime.now(),
                    processing_time_ms=int(processing_time),
                    retry_count=retry_count
                )
                
                self.processing_results[event_id] = result
                self.metrics['events_processed'] += 1
                self._update_average_processing_time(processing_time)
                
                self.log_info(f"Event processed successfully: {event_type}", {
                    'event_id': event_id,
                    'retry_count': retry_count,
                    'processing_time_ms': int(processing_time)
                })
                
                return
                
            except Exception as e:
                retry_count += 1
                
                self.log_warning(f"Event processing failed (attempt {retry_count}): {event_type}", {
                    'event_id': event_id,
                    'error': str(e),
                    'retry_count': retry_count
                })
                
                if retry_count <= subscription.max_retries:
                    # Wait before retry
                    await asyncio.sleep(subscription.retry_delay_seconds)
                else:
                    # Max retries reached - send to dead letter queue
                    await self._send_to_dead_letter_queue(event_data, str(e), retry_count)
                    break
        
        # Record failed processing
        processing_time = (datetime.now() - start_time).total_seconds() * 1000
        result = EventProcessingResult(
            event_id=event_id,
            success=False,
            processed_at=datetime.now(),
            processing_time_ms=int(processing_time),
            retry_count=retry_count,
            error_message=str(e) if 'e' in locals() else 'Unknown error'
        )
        
        self.processing_results[event_id] = result
        self.metrics['events_failed'] += 1
    
    async def _send_to_dead_letter_queue(selfcount: int):
        """Send failed event to dead letter queue"""
        dead_letter_event = {
            'original_event': event_data,
            'failure_reason': error_message,
            'retry_count': retry_count,
            'failed_at': datetime.now().isoformat(),
            'tenant_id': str(self.tenant.id)
        }
        
        self.failed_events.append(dead_letter_event)
        
        # Optionally persist to database or external dead letter queue
        await self._persist_dead_letter_event(dead_letter_event)
        
        self.log_error("Event sent to dead letter queue", None, {
            'event_id': event_data.get('event_id'),
            'event_type': event_data.get('event_type'),
            'retry_count': retry_count
        })
    
    async def retry_failed_events(self, max_age_hours: int = 24) -> Dict[str, Any]:
        """Retry events from dead letter queue"""
        from datetime import timedelta
        
        cutoff_time = datetime.now() - timedelta(hours=max_age_hours)
        retry_results = {
            'attempted': 0,
            'successful': 0,
            'still_failed': 0
        }
        
        events_to_retry = []
        remaining_events = []
        
        for dead_event in self.failed_events:
            failed_at = datetime.fromisoformat(dead_event['failed_at'])
            
            if failed_at >= cutoff_time:
                events_to_retry.append(dead_event)
            else:
                remaining_events.append(dead_event)
        
        # Update failed events list
        self.failed_events = remaining_events
        
        # Retry events
        for dead_event in events_to_retry:
            retry_results['attempted'] += 1
            
            try:
                original_event = dead_event['original_event']
                await self._process_event_with_retry(original_event)
                retry_results['successful'] += 1
                
            except Exception as e:
                retry_results['still_failed'] += 1
                # Add back to failed events
                self.failed_events.append(dead_event)
        
        self.log_info("Dead letter queue retry completed", retry_results)
        return retry_results
    
    def get_processing_metrics(self) -> Dict[str, Any]:
        """Get event processing metrics"""
        return {
            **self.metrics,
            'failed_events_count': len(self.failed_events),
            'active_subscriptions': len(self.subscriptions),
            'recent_processing_results': list(self.processing_results.values())[-10:]
        }
    
    def get_event_processing_status(self, event_id: str) -> Optional[EventProcessingResult]:
        """Get processing status for specific event"""
        return self.processing_results.get(event_id)
    
    async def _wait_for_processing_confirmation(self, event_id: str, timeout_seconds: int = 30):
        """Wait for event processing confirmation"""
        import asyncio
        
        for _ in range(timeout_seconds):
            if event_id in self.processing_results:
                return self.processing_results[event_id]
            
            await asyncio.sleep(1)
        
        raise TimeoutError(f"Event processing confirmation timeout: {event_id}")
    
    def _update_average_processing_time(self, processing_time: float):
        """Update average processing time metric"""
        current_avg = self.metrics['average_processing_time']
        processed_count = self.metrics['events_processed']
        
        # Calculate new average
        self.metrics['average_processing_time'] = (
            (current_avg * (processed_count - 1) + processing_time) / processed_count
        )
    
    async def _persist_dead_letter_event(self, dead_letter_event: Dict[str, Any]):
        """Persist dead letter event for analysis"""
        # This would save to database or external system
        # For now, just log it
        self.log_warning("Dead letter event persisted", None, dead_letter_event)