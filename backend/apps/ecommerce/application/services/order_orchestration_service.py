"""
Order Orchestration Service
Coordinates complex workflows across multiple domains
"""

from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
import asyncio
from dataclasses import dataclass

from ...domain.entities.order import Order
from ...domain.entities.cart import Cart
from ...domain.events.order_events import (
    OrderCreatedEvent, OrderPaymentProcessedEvent, OrderFulfilledEvent,
    OrderCancelledEvent, OrderRefundedEvent
)
from ...domain.events.inventory_events import InventoryReservedEvent, InventoryReleasedEvent
from ...domain.events.customer_events import CustomerOrderCompletedEvent
from ...infrastructure.messaging.publishers import EventPublisher
from ...infrastructure.messaging.subscribers import EventSubscriber
from ...infrastructure.external.payment.payment_processor import PaymentProcessor
from ...infrastructure.external.shipping.shipping_calculator import ShippingCalculator
from ...infrastructure.external.inventory.stock_sync import StockSync
from ..use_cases.orders.create_order import CreateOrderUseCase
from ..use_cases.orders.fulfill_order import FulfillOrderUseCase
from ..use_cases.orders.cancel_order import CancelOrderUseCase
from ..use_cases.notifications.send_notification import SendNotificationUseCase
from .base import BaseApplicationService


@dataclass
class OrderWorkflowContext:
    """Context for order workflow"""
    order_id: str
    user_id: Optional[str]
    cart_id: Optional[str] = None
    workflow_state: str = 'initiated'
    error_count: int = 0
    max_retries: int = 3
    created_at: datetime = None
    
    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now()


class OrderOrchestrationService(BaseApplicationService):
    """Service for orchestrating complex order workflows"""
    
    def __init__(self, tenant):
        super().__init__(tenant)
        self.payment_processor = PaymentProcessor(tenant)
        self.shipping_calculator = ShippingCalculator(tenant)
        self.stock_sync = StockSync(tenant)
        self.event_publisher = EventPublisher(tenant)
        self.event_subscriber = EventSubscriber(tenant)
        self.notification_service = SendNotificationUseCase(tenant)
        
        # Workflow state management
        self.active_workflows: Dict[str, OrderWorkflowContext] = {}
        
        # Register event handlers
        self._register_event_handlers()
    
    async def orchestrate_order_creation(self, cart], 
                                       user_id: Optional[str] = None) -> Dict[str, Any]:
        """Orchestrate complete order creation workflow"""
        workflow_id = f"order_workflow_{cart_id}_{datetime.now().timestamp()}"
        
        try:
            # Initialize workflow context
            context = OrderWorkflowContext(
                order_id="",  # Will be set after order creation
                user_id=user_id,
                cart_id=cart_id,
                payment_data=order_data.get('payment'),
                shipping_data=order_data.get('shipping')
            )
            self.active_workflows[workflow_id] = context
            
            self.log_info(f"Starting order workflow: {workflow_id}")
            
            # Step 1: Validate and reserve inventory
            inventory_result = await self._reserve_inventory(context)
            if not inventory_result['success']:
                raise WorkflowError("Inventory reservation failed", inventory_result['details'])
            
            # Step 2: Calculate final pricing (taxes, shipping, discounts)
            pricing_result = await self._calculate_final_pricing(context, order_data)
            order_data.update(pricing_result)
            
            # Step 3: Create order entity
            order_result = await self._create_order(context, order_data)
            context.order_id = order_result['order_id']
            context.workflow_state = 'order_created'
            
            # Step 4: Process payment
            if_result = await self._process_payment(context)
                if not payment_result['success']:
                    await self._handle_payment_failure(context, payment_result)
                    raise WorkflowError("Payment processing failed", payment_result['details'])
            
            # Step 5: Confirm inventory reservation
            await self._confirm_inventory_reservation(context, inventory_result['reservations'])
            
            # Step 6: Initialize fulfillment process
            await self._initialize_fulfillment(context)
            
            # Step 7: Send confirmations
            await self._send_order_confirmations(context)
            
            # Step 8: Clean up workflow
            context.workflow_state = 'completed'
            self._cleanup_workflow(workflow_id)
            
            self.log_info(f"Order workflow completed successfully: {workflow_id}")
            
            return {
                'success': True,
                'order_id': context.order_id,
                'workflow_id': workflow_id,
                'status': 'completed'
            }
            
        except WorkflowError as e:
            await self._handle_workflow_error(workflow_id, context, e)
            raise
        except Exception as e:
            await self._handle_workflow_error(workflow_id, context, e)
            raise WorkflowError(f"Order workflow failed: {str(e)}")
    
    async def orchestrate_order_fulfillment(self, order_id: str, fulf -> Dict[str, Any]:
        """Orchestrate order fulfillment workflow"""
        workflow_id = f"fulfillment_workflow_{order_id}_{datetime.now().timestamp()}"
        
        try:
            context = OrderWorkflowContext(
                order_id=order_id,
                workflow_state='fulfillment_initiated'
            )
            self.active_workflows[workflow_id] = context
            
            # Step 1: Validate order can be fulfilled
            validation_result = await self._validate_fulfillment(context, fulfillment_data)
            if not validation_result['success']:
                raise WorkflowError("Fulfillment validation failed", validation_result['details'])
            
            # Step 2: Allocate inventory
            allocation_result = await self._allocate_inventory(context)
            
            # Step 3: Generate shipping labels
            shipping_result = await self._generate_shipping_labels(context, fulfillment_data)
            
            # Step 4: Update order status
            await self._update_order_fulfillment_status(context, 'processing')
            
            # Step 5: Create shipment tracking
            tracking_result = await self._create_shipment_tracking(context, shipping_result)
            
            # Step 6: Send fulfillment notifications
            await self._send_fulfillment_notifications(context, tracking_result)
            
            # Step 7: Schedule follow-up workflows
            await self._schedule_fulfillment_followups(context)
            
            context.workflow_state = 'completed'
            self._cleanup_workflow(workflow_id)
            
            return {
                'success': True,
                'order_id': order_id,
                'tracking_number': tracking_result.get('tracking_number'),
                'estimated_delivery': tracking_result.get('estimated_delivery')
            }
            
        except Exception as e:
            await self._handle_workflow_error(workflow_id, context, e)
            raise
    
    async def orchestrate_order_cancellation(self, order_id: str, cancellation_ Optional[str] = None) -> Dict[str, Any]:
        """Orchestrate order cancellation workflow"""
        workflow_id = f"cancellation_workflow_{order_id}_{datetime.now().timestamp()}"
        
        try:
            context = OrderWorkflowContext(
                order_id=order_id,
                user_id=user_id,
                workflow_state='cancellation_initiated'
            )
            self.active_workflows[workflow_id] = context
            
            # Step 1: Validate cancellation is allowed
            validation_result = await self._validate_cancellation(context, cancellation_data)
            if not validation_result['success']:
                raise WorkflowError("Cancellation not allowed", validation_result['details'])
            
            # Step 2: Stop any active fulfillment
            await self._stop_fulfillment_processes(context)
            
            # Step 3: Release inventory
            await self._release_order_inventory(context)
            
            # Step 4: Process refunds if payment was made
            refund_result = await self._process_refund(context, cancellation_data)
            
            # Step 5: Update order status
            await self._update_order_status(context, 'cancelled')
            
            # Step 6: Send cancellation notifications
            await self._send_cancellation_notifications(context, refund_result)
            
            # Step 7: Update customer analytics
            await self._update_customer_analytics(context, 'cancellation')
            
            context.workflow_state = 'completed'
            self._cleanup_workflow(workflow_id)
            
            return {
                'success': True,
                'order_id': order_id,
                'refund_amount': refund_result.get('amount', 0),
                'refund_status': refund_result.get('status', 'pending')
            }
            
        except Exception as e:
            await self._handle_workflow_error(workflow_id, context, e)
            raise
    
    # Private workflow step methods
    async def _reserve_inventory(self, context: OrderWorkflowContext) -> Dict[str, Any]:
        """Reserve inventory for order items"""
        try:
            # This would integrate with inventory service
            reservations = await self.stock_sync.reserve_cart_items(context.cart_id)
            
            # Publish inventory reserved event
            event = InventoryReservedEvent(
                cart_id=context.cart_id,
                reservations=reservations,
                expires_at=datetime.now() + timedelta(minutes=15),
                timestamp=datetime.now()
            )
            await self.event_publisher.publish_async(event)
            
            return {
                'success': True,
                'reservations': reservations
            }
            
        except Exception as e:
            self.log_error("Inventory reservation failed", e)
            return {
                'success': False,
                'details': str(e)
            }
    
    async def _calculate_final_pricing(self, context: OrderWorkflowContext, [str, Any]:
        """Calculate final pricing including taxes and shipping"""
        try:
            # Calculate shipping
            shipping_cost = await self.shipping_calculator.calculate_shipping(
                cart_id=context.cart_id,
                shipping_address=order_data.get('shipping_address'),
                shipping_method=context.shipping_data.get('method') if context.shipping_data else None
            )
            
            # Calculate taxes
            tax_amount = await self._calculate_taxes(context, order_data)
            
            # Apply final discounts
            discount_amount = await self._apply_final_discounts(context, order_data)
            
            return {
                'shipping_cost': shipping_cost,
                'tax_amount': tax_amount,
                'discount_amount': discount_amount
            }
            
        except Exception as e:
            self.log_error("Pricing calculation failed", e)
            raise
    
    async def _create_order(self, context: OrderWorkflowContext, 
                , Any]) -> Dict[str, Any]:
        """Create order entity"""
        try:
            create_use_case = CreateOrderUseCase(self.tenant)
            result = create_use_case.execute(order_data, context.user_id)
            
            return {
                'success': True,
                'order_id': result.id
            }
            
        except Exception as e:
            self.log_error("Order creation failed", e)
            raise
    
    async def _process_payment(self, context: OrderWorkflowContext) -> Dict[str, Any]:
        """Process payment for order"""
        try:
            payment_result = await self.payment_processor.process_payment_async({
                'order_id': context.order_id,
                **context.payment_data
            })
            
            # Publish payment processed event
            event = OrderPaymentProcessedEvent(
                order_id=context.order_id,
                payment_status=payment_result['status'],
                transaction_id=payment_result.get('transaction_id'),
                amount=payment_result.get('amount'),
                timestamp=datetime.now()
            )
            await self.event_publisher.publish_async(event)
            
            return payment_result
            
        except Exception as e:
            self.log_error("Payment processing failed", e)
            return {
                'success': False,
                'details': str(e)
            }
    
    async def _handle_payment_failure(self, context: OrderWorkflowContext, 
                                    payment_result: Dict[str, Any]):
        """Handle payment failure"""
        # Release inventory reservations
        await self._release_inventory_reservations(context)
        
        # Send payment failure notification
        await self.notification_service.execute({
            'type': 'payment_failed',
            'recipient': context.user_id,
            'order_id': context.order_id,
            'failure_reason': payment_result.get('details')
        })
        
        # Update order status
        await self._update_order_status(context, 'payment_failed')
    
    # Event Handlers Registration
    def _register_event_handlers(self):
        """Register event handlers for this service"""
        self.event_subscriber.subscribe('OrderCreatedEvent', self._handle_order_created)
        self.event_subscriber.subscribe('OrderPaymentProcessedEvent', self._handle_payment_processed)
        self.event_subscriber.subscribe('InventoryUpdatedEvent', self._handle_inventory_updated)
        self.event_subscriber.subscribe('ShippingStatusUpdatedEvent', self._handle_shipping_updated)
    
    async def _handle_order_created(self, event: OrderCreatedEvent):
        """Handle order created event"""
        try:
            # Start background processes
            await self._start_fraud_detection(event.order_id)
            await self._update_customer_analytics(None, 'order_created', event.order_id)
            await self._schedule_follow_up_emails(event.order_id)
            
        except Exception as e:
            self.log_error("Error handling order created event", e)
    
    async def _handle_payment_processed(self, event: OrderPaymentProcessedEvent):
        """Handle payment processed event"""
        try:
            if event.payment_status == 'success':
                # Trigger fulfillment process
                await self._initialize_fulfillment_from_payment(event.order_id)
            else:
                # Handle payment failure
                await self._handle_payment_failure_event(event)
                
        except Exception as e:
            self.log_error("Error handling payment processed event", e)
    
    async def _start_fraud_detection(self, order_id: str):
        """Start fraud detection analysis"""
        # This would integrate with fraud detection service
        self.log_info(f"Starting fraud detection for order: {order_id}")
    
    async def _schedule_follow_up_emails(self, order_id: str):
        """Schedule follow-up email campaigns"""
        # Schedule review request email for 7 days after delivery
        # Schedule repurchase suggestion for 30 days
        self.log_info(f"Scheduling follow-up emails for order: {order_id}")