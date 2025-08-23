"""
Cross-Domain Event Handlers
Handle events that span multiple domains
"""

from typing import Dict, Any, Optional
import asyncio
from datetime import datetime, timedelta

from ...domain.events.product_events import (
    ProductCreatedEvent, ProductUpdatedEvent, ProductDeletedEvent,
    ProductPriceChangedEvent, ProductStockChangedEvent
)
from ...domain.events.order_events import (
    OrderCreatedEvent, OrderFulfilledEvent, OrderCancelledEvent
)
from ...domain.events.cart_events import (
    ItemAddedToCartEvent, CartAbandonedEvent
)
from ...domain.events.inventory_events import (
    InventoryUpdatedEvent, LowStockAlertEvent, StockOutEvent
)
from ...domain.events.customer_events import (
    CustomerRegisteredEvent, CustomerOrderCompletedEvent
)
from ...infrastructure.messaging.subscribers import EventSubscriber
from ...infrastructure.ai.recommendations.real_time_recommendations import RealTimeRecommender
from ...infrastructure.ai.pricing.dynamic_pricing_engine import DynamicPricingEngine
from ...infrastructure.ai.personalization.customer_segmentation import CustomerSegmentation
from ...infrastructure.external.analytics.analytics_tracker import AnalyticsTracker
from ..use_cases.notifications.send_notification import SendNotificationUseCase
from ..use_cases.analytics.update_metrics import UpdateMetricsUseCase
from .base import BaseEventHandler


class ProductEventHandler(BaseEventHandler):
    """Handler for product-related events across domains"""
    
    def __init__(self, tenant):
        super().__init__(tenant)
        self.recommender = RealTimeRecommender(tenant)
        self.pricing_engine = DynamicPricingEngine(tenant)
        self.analytics_tracker = AnalyticsTracker(tenant)
        self.notification_service = SendNotificationUseCase(tenant)
        self.metrics_service = UpdateMetricsUseCase(tenant)
    
    async def handle_product_created(self, event: ProductCreatedEvent):
        """Handle product created event"""
        try:
            # Start AI analysis pipeline
            await self._initialize_product_ai_analysis(event)
            
            # Update search index
            await self._update_search_index(event.product_id, 'create')
            
            # Notify relevant customers about new product
            await self._notify_interested_customers(event)
            
            # Update category metrics
            await self._update_category_metrics(event.product_id)
            
            # Track analytics event
            await self.analytics_tracker.track_event({
                'event': 'product_created',
                'product_id': event.product_id,
                'tenant_id': event.tenant_id,
                'timestamp': event.timestamp
            })
            
        except Exception as e:
            self.log_error("Error handling product created event", e)
    
    async def handle_product_price_changed(self, event: ProductPriceChangedEvent):
        """Handle product price changed event"""
        try:
            # Update dependent pricing calculations
            await self._recalculate_bundle_prices(event.product_id)
            
            # Notify customers with this item in wishlist
            await self._notify_wishlist_price_drop(event)
            
            # Update cart items with new pricing
            await self._update_cart_pricing(event.product_id, event.new_price)
            
            # Trigger competitor price analysis
            await self.pricing_engine.analyze_competitor_response(
                event.product_id, event.old_price, event.new_price
            )
            
            # Update recommendation weights
            await self.recommender.update_price_factor(event.product_id, event.new_price)
            
        except Exception as e:
            self.log_error("Error handling product price changed event", e)
    
    async def handle_product_stock_changed(self, event: ProductStockChangedEvent):
        """Handle product stock changed event"""
        try:
            # Check for low stock alerts
            if event.new_stock <= event.low_stock_threshold:
                await self._trigger_low_stock_alert(event)
            
            # Update availability in search index
            await self._update_search_availability(event.product_id, event.new_stock > 0)
            
            # Notify back-in-stock subscribers if stock was 0 and now > 0
            if event.old_stock == 0 and event.new_stock > 0:
                await self._notify_back_in_stock(event.product_id)
            
            # Update demand forecasting data
            await self._update_demand_forecast(event)
            
        except Exception as e:
            self.log_error("Error handling product stock changed event", e)
    
    async def _initialize_product_ai_analysis(self, event: ProductCreatedEvent):
        """Initialize AI analysis for new product"""
        # Start content analysis for recommendations
        await self.recommender.analyze_product_content(event.product_id)
        
        # Initialize pricing optimization
        await self.pricing_engine.initialize_product_pricing(event.product_id)
        
        # Add to demand forecasting model
        await self._add_to_demand_model(event.product_id)
    
    async def _notify_interested_customers(self, event: ProductCreatedEvent):
        """Notify customers who might be interested in new product"""
        # Find customers with similar purchase history
        interested_customers = await self._find_interested_customers(event.product_id)
        
        for customer_id in interested_customers:
            await self.notification_service.execute({
                'type': 'new_product_recommendation',
                'recipient': customer_id,
                'product_id': event.product_id,
                'reason': 'based_on_purchase_history'
            })


class OrderEventHandler(BaseEventHandler):
    """Handler for order-related events across domains"""
    
    def __init__(self, tenant):
        super().__init__(tenant)
        self.customer_segmentation = CustomerSegmentation(tenant)
        self.recommender = RealTimeRecommender(tenant)
        self.analytics_tracker = AnalyticsTracker(tenant)
        self.metrics_service = UpdateMetricsUseCase(tenant)
    
    async def handle_order_created(self, event: OrderCreatedEvent):
        """Handle order created event"""
        try:
            # Update customer lifetime value
            await self._update_customer_ltv(event.user_id, event.total_amount)
            
            # Update product sales metrics
            await self._update_product_sales_metrics(event.order_id)
            
            # Trigger inventory updates
            await self._update_inventory_after_order(event.order_id)
            
            # Update recommendation models
            await self._update_recommendation_models(event)
            
            # Start customer journey tracking
            await self._track_customer_journey(event)
            
            # Schedule post-purchase workflows
            await self._schedule_post_purchase_workflows(event)
            
        except Exception as e:
            self.log_error("Error handling order created event", e)
    
    async def handle_order_fulfilled(self, event: OrderFulfilledEvent):
        """Handle order fulfilled event"""
        try:
            # Update delivery analytics
            await self._update_delivery_metrics(event.order_id)
            
            # Schedule review request
            await self._schedule_review_request(event.order_id)
            
            # Update customer satisfaction tracking
            await self._track_fulfillment_satisfaction(event)
            
            # Trigger replenishment recommendations
            await self._trigger_replenishment_analysis(event.order_id)
            
        except Exception as e:
            self.log_error("Error handling order fulfilled event", e)
    
    async def _update_customer_ltv(self, user_id: Optional[str], order_amount: float):
        """Update customer lifetime value"""
        if not user_id:
            return
        
        await self.customer_segmentation.update_customer_value(user_id, order_amount)
    
    async def _update_recommendation_models(self, event: OrderCreatedEvent):
        """Update recommendation models with purchase data"""
        # Update collaborative filtering model
        await self.recommender.update_purchase_matrix(
            event.user_id, event.order_id, event.item_count
        )
        
        # Update trending products
        await self.recommender.update_trending_scores(event.order_id)


class CartEventHandler(BaseEventHandler):
    """Handler for cart-related events"""
    
    def __init__(self, tenant):
        super().__init__(tenant)
        self.recommender = RealTimeRecommender(tenant)
        self.notification_service = SendNotificationUseCase(tenant)
    
    async def handle_item_added_to_cart(self, event: ItemAddedToCartEvent):
        """Handle item added to cart event"""
        try:
            # Generate cross-sell recommendations
            recommendations = await self.recommender.generate_cross_sell_recommendations(
                event.product_id, event.cart_id
            )
            
            # Update product view frequency
            await self._update_product_metrics(event.product_id, 'cart_add')
            
            # Track conversion funnel
            await self._track_conversion_step(event.user_id, 'added_to_cart')
            
            # Schedule abandonment recovery if first item
            await self._schedule_abandonment_recovery(event.cart_id)
            
        except Exception as e:
            self.log_error("Error handling item added to cart event", e)
    
    async def handle_cart_abandoned(self, event: CartAbandonedEvent):
        """Handle cart abandoned event"""
        try:
            # Calculate recovery probability
            recovery_probability = await self._calculate_recovery_probability(event.cart_id)
            
            # Schedule recovery email sequence
            await self._schedule_recovery_emails(event, recovery_probability)
            
            # Update abandonment analytics
            await self._update_abandonment_metrics(event)
            
            # Generate discount recommendations
            await self._generate_recovery_discount(event.cart_id, event.cart_value)
            
        except Exception as e:
            self.log_error("Error handling cart abandoned event", e)
    
    async def _schedule_recovery_emails(self, event: CartAbandonedEvent, probability: float):
        """Schedule cart recovery email sequence"""
        recovery_schedule = [
            {'delay_hours': 1, 'template': 'cart_reminder'},
            {'delay_hours': 24, 'template': 'cart_discount_offer'},
            {'delay_hours': 72, 'template': 'cart_final_reminder'}
        ]
        
        for schedule in recovery_schedule:
            await self.notification_service.schedule({
                'type': 'cart_recovery',
                'template': schedule['template'],
                'recipient': event.user_id,
                'cart_id': event.cart_id,
                'delay_hours': schedule['delay_hours'],
                'recovery_probability': probability
            })


class InventoryEventHandler(BaseEventHandler):
    """Handler for inventory-related events"""
    
    def __init__(self, tenant):
        super().__init__(tenant)
        self.notification_service = SendNotificationUseCase(tenant)
        self.pricing_engine = DynamicPricingEngine(tenant)
    
    async def handle_low_stock_alert(self, event: LowStockAlertEvent):
        """Handle low stock alert event"""
        try:
            # Notify inventory managers
            await self._notify_inventory_managers(event)
            
            # Adjust pricing for scarcity
            await self.pricing_engine.apply_scarcity_pricing(
                event.product_id, event.current_stock
            )
            
            # Pause marketing campaigns for out-of-stock items
            await self._pause_marketing_campaigns(event.product_id)
            
            # Update search ranking to reduce visibility
            await self._adjust_search_ranking(event.product_id, 'low_stock')
            
        except Exception as e:
            self.log_error("Error handling low stock alert event", e)
    
    async def handle_stock_out(self, event: StockOutEvent):
        """Handle stock out event"""
        try:
            # Notify back-in-stock subscribers
            subscribers = await self._get_back_in_stock_subscribers(event.product_id)
            
            # Create backorder opportunities
            await self._create_backorder_option(event.product_id)
            
            # Update recommendation weights (reduce visibility)
            await self.recommender.update_availability_factor(event.product_id, False)
            
            # Trigger supplier reorder workflow
            await self._trigger_reorder_workflow(event.product_id)
            
        except Exception as e:
            self.log_error("Error handling stock out event", e)


class CustomerEventHandler(BaseEventHandler):
    """Handler for customer-related events"""
    
    def __init__(self, tenant):
        super().__init__(tenant)
        self.customer_segmentation = CustomerSegmentation(tenant)
        self.recommender = RealTimeRecommender(tenant)
        self.notification_service = SendNotificationUseCase(tenant)
    
    async def handle_customer_registered(self, event: CustomerRegisteredEvent):
        """Handle new customer registration event"""
        try:
            # Initialize customer profile
            await self.customer_segmentation.initialize_customer_profile(event.user_id)
            
            # Send welcome sequence
            await self._start_welcome_sequence(event.user_id)
            
            # Generate initial recommendations
            await self._generate_new_customer_recommendations(event.user_id)
            
            # Start behavior tracking
            await self._initialize_behavior_tracking(event.user_id)
            
        except Exception as e:
            self.log_error("Error handling customer registered event", e)
    
    async def handle_customer_order_completed(self, event: CustomerOrderCompletedEvent):
        """Handle customer order completion event"""
        try:
            # Update customer segment
            new_segment = await self.customer_segmentation.update_customer_segment(
                event.user_id, event.order_amount
            )
            
            # Trigger loyalty program updates
            await self._update_loyalty_points(event.user_id, event.order_amount)
            
            # Schedule post-purchase recommendations
            await self._schedule_post_purchase_recommendations(event)
            
            # Update customer journey stage
            await self._update_customer_journey_stage(event.user_id, 'post_purchase')
            
        except Exception as e:
            self.log_error("Error handling customer order completed event", e)


class AIEventHandler(BaseEventHandler):
    """Handler for AI and ML related events"""
    
    def __init__(self, tenant):
        super().__init__(tenant)
        self.recommender = RealTimeRecommender(tenant)
        self.pricing_engine = DynamicPricingEngine(tenant)
    
    async def handle_recommendation_generated(self, event):
        """Handle recommendation generated event"""
        try:
            # Track recommendation performance
            await self._track_recommendation_metrics(event)
            
            # Update model feedback loop
            await self._update_recommendation_feedback(event)
            
        except Exception as e:
            self.log_error("Error handling recommendation generated event", e)
    
    async def handle_price_optimization_completed(self, event):
        """Handle price optimization completion event"""
        try:
            # Apply optimized prices
            await self._apply_optimized_prices(event.price_changes)
            
            # Schedule performance monitoring
            await self._monitor_pricing_performance(event.optimization_id)
            
        except Exception as e:
            self.log_error("Error handling price optimization completed event", e)