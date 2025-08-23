"""
Advanced Message Queue Implementation
Redis-based with fallback to database
"""

import redis
import json
import asyncio
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
import logging

from django.conf import settings
from django.db import models
from ...domain.events.base import DomainEvent
from .base import BaseMessageQueue


@dataclass
class QueueMessage:
    """Message wrapper for queue operations"""
    id: str
    topic: str
    payload: Dict[str, Any]
    created_at: datetime
    scheduled_for: Optional[datetime] = None
    retry_count: int = 0
    max_retries: int = 3
    priority: int = 5  # 1-10, higher = more important
    headers: Dict[str, str] = None
    
    def __post_init__(self):
        if self.headers is None:
            self.headers = {}


class RedisMessageQueue(BaseMessageQueue):
    """Redis-based message queue with advanced features"""
    
    def __init__(self, tenant):
        super().__init__(tenant)
        self.redis_client = self._get_redis_client()
        self.dead_letter_queue = f"dlq:{tenant.id}"
        self.scheduled_queue = f"scheduled:{tenant.id}"
        self.retry_queue = f"retry:{tenant.id}"
        
        # Queue configuration
        self.queues = {
            'high_priority': f"queue:high:{tenant.id}",
            'normal_priority': f"queue:normal:{tenant.id}",
            'low_priority': f"queue:low:{tenant.id}",
            'events': f"queue:events:{tenant.id}",
            'analytics': f"queue:analytics:{tenant.id}",
            'notifications': f"queue:notifications:{tenant.id}"
        }
        
        # Consumer tracking
        self.consumers: Dict[str, Callable] = {}
        self.running = False
        
    def _get_redis_client(self):
        """Get Redis client with proper configuration"""
        return redis.Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            db=settings.REDIS_DB,
            password=settings.REDIS_PASSWORD,
            decode_responses=True,
            socket_connect_timeout=5,
            socket_timeout=5,
            retry_on_timeout=True
        )
    
    async def publish(self, message: QueueMessage) -> bool:
        """Publish message to appropriate queue"""
        try:
            # Determine target queue based on priority and type
            target_queue = self._get_target_queue(message)
            
            # Serialize message
            serialized = json.dumps(asdict(message), default=str)
            
            if message.scheduled_for and message.scheduled_for > datetime.now():
                # Schedule for future delivery
                score = message.scheduled_for.timestamp()
                self.redis_client.zadd(self.scheduled_queue, {serialized: score})
            else:
                # Immediate delivery
                if message.priority > 7:
                    # High priority - add to front
                    self.redis_client.lpush(target_queue, serialized)
                else:
                    # Normal/low priority - add to back
                    self.redis_client.rpush(target_queue, serialized)
            
            self.log_info(f"Message published to {target_queue}", {
                'message_id': message.id,
                'topic': message.topic
            })
            
            return True
            
        except Exception as e:
            self.log_error("Failed to publish message", e)
            return False
    
    async def publish_batch(self, messages: List[QueueMessage]) -> Dict[str, bool]:
        """Publish multiple messages efficiently"""
        results = {}
        
        try:
            # Group messages by target queue
            queue_groups = {}
            scheduled_messages = []
            
            for msg in messages:
                if msg.scheduled_for and msg.scheduled_for > datetime.now():
                    scheduled_messages.append(msg)
                else:
                    target_queue = self._get_target_queue(msg)
                    if target_queue not in queue_groups:
                        queue_groups[target_queue] = []
                    queue_groups[target_queue].append(msg)
            
            # Use Redis pipeline for efficiency
            pipe = self.redis_client.pipeline()
            
            # Add scheduled messages
            if scheduled_messages:
                scheduled_data = {}
                for msg in scheduled_messages:
                    serialized = json.dumps(asdict(msg), default=str)
                    score = msg.scheduled_for.timestamp()
                    scheduled_data[serialized] = score
                    results[msg.id] = True
                
                pipe.zadd(self.scheduled_queue, scheduled_data)
            
            # Add immediate messages
            for queue_name, queue_messages in queue_groups.items():
                high_priority = []
                normal_priority = []
                
                for msg in queue_messages:
                    serialized = json.dumps(asdict(msg), default=str)
                    if msg.priority > 7:
                        high_priority.append(serialized)
                    else:
                        normal_priority.append(serialized)
                    results[msg.id] = True
                
                if high_priority:
                    pipe.lpush(queue_name, *high_priority)
                if normal_priority:
                    pipe.rpush(queue_name, *normal_priority)
            
            # Execute all operations
            pipe.execute()
            
            self.log_info(f"Batch published {len(messages)} messages")
            return results
            
        except Exception as e:
            self.log_error("Batch publish failed", e)
            # Mark all as failed
            return {msg.id: False for msg in messages}
    
    async def consume(self, queue_name: str, handler: Callable, 
                     batch_size: int = 1, timeout: int = 10) -> None:
        """Consume messages from queue"""
        queue_key = self.queues.get(queue_name, queue_name)
        self.consumers[queue_name] = handler
        
        self.log_info(f"Starting consumer for {queue_name}")
        
        while self.running:
            try:
                # Process scheduled messages first
                await self._process_scheduled_messages()
                
                # Get messages from queue
                if batch_size == 1:
                    # Single message processing
                    message_data = self.redis_client.blpop(queue_key, timeout=timeout)
                    if messagemsg = message_data
                        await self._process_message(serialized_msg, handler)
                else:
                    # Batch processing
                    messages = []
                    for _ in range(batch_size):
                        msg_data = self.redis_client.lpop(queue_key)
                            messages.append(msg_data)
                        else:
                            break
                    
                    if messages:
                        await self._process_message_batch(messages, handler)
                
            except Exception as e:
                self.log_error(f"Consumer error for {queue_name}", e)
                await asyncio.sleep(1)  # Brief pause before retry
    
    async def _process_message(self, serialized_msg: str, handler: Callable):
        """Process individual message with retry logic"""
        try:
            # Deserialize message
            msg_data = json.loads(serialized_msg)
            message = QueueMessage(**msg_data)
            
            # Process with handler
            success = await self._execute_handler(handler, message)
            
            if success:
                self.log_info(f"Message processed successfully: {message.id}")
            else:
                await self._handle_processing_failure(message, serialized_msg)
                
        except Exception as e:
            self.log_error("Message processing failed", e)
            # Try to parse message for retry logic
            try:
                msg_data = json.loads(serialized_msg)
                message = QueueMessage(**msg_data)
                await self._handle_processing_failure(message, serialized_msg)
            except:
                # Can't parse message - send to DLQ
                self.redis_client.lpush(self.dead_letter_queue, serialized_msg)
    
    async def _process_message_batch(self, messages: List[str], handler: Callable):
        """Process batch of messages"""
        parsed_messages = []
        
        for serialized_msg in messages:
            try:
                msg_data = json.loads(serialized_msg)
                message = QueueMessage(**msg_data)
                parsed_messages.append((message, serialized_msg))
            except Exception as e:
                # Invalid message - send to DLQ
                self.redis_client.lpush(self.dead_letter_queue, serialized_msg)
        
        # Process batch
        if parsed_messages:
            try:
                success = await handler([msg for msg, _ in parsed_messages])
                if not success:
                    # Retry individually
                    for message, serialized_msg in parsed_messages:
                        await self._handle_processing_failure(message, serialized_msg)
            except Exception as e:
                self.log_error("Batch processing failed", e)
                for message, serialized_msg in parsed_messages:
                    await self._handle_processing_failure(message, serialized_msg)
    
    async def _process_scheduled_messages(self):
        """Process messages scheduled for current time"""
        try:
            current_time = datetime.now().timestamp()
            
            # Get messages ready for processing
            ready_messages = self.redis_client.zrangebyscore(
                self.scheduled_queue, 0, current_time, withscores=False
            )
            
            if ready_messages:
                # Remove from scheduled queue
                self.redis_client.zremrangebyscore(self.scheduled_queue, 0, current_time)
                
                # Add to appropriate processing queues
                for serialized_msg in ready_messages:
                    try:
                        msg_data = json.loads(serialized_msg)
                        message = QueueMessage(**msg_data)
                        target_queue = self._get_target_queue(message)
                        
                        if message.priority > 7:
                            self.redis_client.lpush(target_queue, serialized_msg)
                        else:
                            self.redis_client.rpush(target_queue, serialized_msg)
                            
                    except Exception as e:
                        # Invalid scheduled message
                        self.redis_client.lpush(self.dead_letter_queue, serialized_msg)
                
                self.log_info(f"Processed {len(ready_messages)} scheduled messages")
                
        except Exception as e:
            self.log_error("Failed to process scheduled messages", e)
    
    async def _handle_processing_failure(self, message: QueueMessage, serialized_msg: str):
        """Handle message processing failure with retry logic"""
        message.retry_count += 1
        
        if message.retry_count <= message.max_retries:
            # Schedule for retry with exponential backoff
            delay_seconds = min(300, 2 ** message.retry_count)  # Max 5 minutes
            retry_time = datetime.now() + timedelta(seconds=delay_seconds)
            
            # Update message with new retry info
            message.scheduled_for = retry_time
            updated_msg = json.dumps(asdict(message), default=str)
            
            # Add to scheduled queue for retry
            score = retry_time.timestamp()
            self.redis_client.zadd(self.scheduled_queue, {updated_msg: score})
            
            self.log_warning(f"Message scheduled for retry {message.retry_count}/{message.max_retries}", {
                'message_id': message.id,
                'retry_delay_seconds': delay_seconds
            })
        else:
            # Max retries exceeded - send to dead letter queue
            self.redis_client.lpush(self.dead_letter_queue, serialized_msg)
            
            self.log_error(f"Message moved to DLQ after {message.retry_count} retries", None, {
                'message_id': message.id,
                'topic': message.topic
            })
    
    def start_consumers(self):
        """Start all registered consumers"""
        self.running = True
        self.log_info("Message queue consumers started")
    
    def stop_consumers(self):
        """Stop all consumers gracefully"""
        self.running = False
        self.log_info("Message queue consumers stopped")
    
    def get_queue_stats(self) -> Dict[str, Any]:
        """Get queue statistics and health info"""
        stats = {
            'queues': {},
            'scheduled_count': self.redis_client.zcard(self.scheduled_queue),
            'dead_letter_count': self.redis_client.llen(self.dead_letter_queue),
            'consumers': list(self.consumers.keys()),
            'redis_info': self._get_redis_info()
        }
        
        for name, queue_key in self.queues.items():
            stats['queues'][name] = {
                'length': self.redis_client.llen(queue_key),
                'consumers': 1 if name in self.consumers else 0
            }
        
        return stats
    
    def _get_target_queue(self, message: QueueMessage) -> str:
        """Determine target queue based on message properties"""
        if message.priority > 7:
            return self.queues['high_priority']
        elif message.priority < 3:
            return self.queues['low_priority']
        elif message.topic in ['analytics', 'metrics']:
            return self.queues['analytics']
        elif 'notification' in message.topic.lower():
            return self.queues['notifications']
        elif 'event' in message.topic.lower():
            return self.queues['events']
        else:
            return self.queues['normal_priority']
    
    async def _execute_handler(self, handler: Callable, message: QueueMessage) -> bool:
        """Execute message handler with error handling"""
        try:
            if asyncio.iscoroutinefunction(handler):
                result = await handler(message)
            else:
                result = handler(message)
            
            return result is not False  # Consider None as success
            
        except Exception as e:
            self.log_error(f"Handler execution failed for message {message.id}", e)
            return False
    
    def _get_redis_info(self) -> Dict[str, Any]:
        """Get Redis connection info"""
        try:
            info = self.redis_client.info()
            return {
                'connected': True,
                'memory_used': info.get('used_memory_human'),
                'connected_clients': info.get('connected_clients'),
                'uptime': info.get('uptime_in_seconds')
            }
        except:
            return {'connected': False}