from datetime import datetime
from typing import Dict, List, Any, Optional
from decimal import Decimal

from .base import DomainEvent


# ============================================================================
# CORE PRODUCT LIFECYCLE EVENTS
# ============================================================================

class ProductCreatedEvent(DomainEvent):
    """Published when a new product is created"""
    
    def __init__(
        self,
        aggregate_id: str,
        sku: str,
        title: str,
        category: str,
        product_type: str,
        initial_price: Decimal,
        initial_stock: int = 0,
        **kwargs
    ):
        super().__init__(aggregate_id, **kwargs)
        self.sku = sku
        self.title = title
        self.category = category
        self.product_type = product_type
        self.initial_price = initial_price
        self.initial_stock = initial_stock
        
        # Event data for serialization
        self.event_data.update({
            'sku': sku,
            'title': title,
            'category': category,
            'product_type': product_type,
            'initial_price': float(initial_price),
            'initial_stock': initial_stock,
            'requires_inventory_tracking': product_type == 'PHYSICAL'
        })


class ProductUpdatedEvent(DomainEvent):
    """Published when product information is updated"""
    
    def __init__(
        self,
        aggregate_id: str,
        sku: str,
        updated_fields: Dict[str, Any],
        **kwargs
    ):
        super().__init__(aggregate_id, **kwargs)
        self.sku = sku
        self.updated_fields = updated_fields
        
        self.event_data.update({
            'sku': sku,
            'updated_fields': updated_fields
        })


class ProductPublishedEvent(DomainEvent):
    """Published when product is made available for sale"""
    
    def __init__(
        self,
        aggregate_id: str,
        sku: str,
        title: str,
        category: str,
        **kwargs
    ):
        super().__init__(aggregate_id, **kwargs)
        self.sku = sku
        self.title = title
        self.category = category
        
        self.event_data.update({
            'sku': sku,
            'title': title,
            'category': category,
            'published_at': self.occurred_at.isoformat()
        })


class ProductUnpublishedEvent(DomainEvent):
    """Published when product is removed from sale"""
    
    def __init__(
        self,
        aggregate_id: str,
        sku: str,
        reason: str = "",
        **kwargs
    ):
        super().__init__(aggregate_id, **kwargs)
        self.sku = sku
        self.reason = reason
        
        self.event_data.update({
            'sku': sku,
            'reason': reason,
            'unpublished_at': self.occurred_at.isoformat()
        })


class ProductDeletedEvent(DomainEvent):
    """Published when product is deleted"""
    
    def __init__(
        self,
        aggregate_id: str,
        sku: str,
        title: str,
        reason: str = "",
        **kwargs
    ):
        super().__init__(aggregate_id, **kwargs)
        self.sku = sku
        self.title = title
        self.reason = reason
        
        self.event_data.update({
            'sku': sku,
            'title': title,
            'reason': reason,
            'deleted_at': self.occurred_at.isoformat()
        })


# ============================================================================
# PRICING EVENTS
# ============================================================================

class ProductPriceUpdatedEvent(DomainEvent):
    """Published when product price is updated"""
    
    def __init__(
        self,
        aggregate_id: str,
        sku: str,
        old_price: Decimal,
        new_price: Decimal,
        currency: str,
        reason: str = "manual_update",
        ai_recommended: bool = False,
        **kwargs
    ):
        super().__init__(aggregate_id, **kwargs)
        self.sku = sku
        self.old_price = old_price
        self.new_price = new_price
        self.currency = currency
        self.reason = reason
        self.ai_recommended = ai_recommended
        self.price_change_percentage = self._calculate_price_change_percentage()
        
        self.event_data.update({
            'sku': sku,
            'old_price': float(old_price),
            'new_price': float(new_price),
            'currency': currency,
            'price_change_amount': float(new_price - old_price),
            'price_change_percentage': self.price_change_percentage,
            'reason': reason,
            'ai_recommended': ai_recommended
        })
    
    def _calculate_price_change_percentage(self) -> float:
        """Calculate percentage change in price"""
        if self.old_price == 0:
            return 0.0
        return float((self.new_price - self.old_price) / self.old_price * 100)


class ProductDiscountAppliedEvent(DomainEvent):
    """Published when discount is applied to product"""
    
    def __init__(
        self,
        aggregate_id: str,
        sku: str,
        discount_type: str,  # 'percentage', 'fixed_amount'
        discount_value: Decimal,
        original_price: Decimal,
        discounted_price: Decimal,
        valid_from: datetime,
        valid_until: Optional[datetime] = None,
        **kwargs
    ):
        super().__init__(aggregate_id, **kwargs)
        self.sku = sku
        self.discount_type = discount_type
        self.discount_value = discount_value
        self.original_price = original_price
        self.discounted_price = discounted_price
        self.valid_from = valid_from
        self.valid_until = valid_until
        
        self.event_data.update({
            'sku': sku,
            'discount_type': discount_type,
            'discount_value': float(discount_value),
            'original_price': float(original_price),
            'discounted_price': float(discounted_price),
            'savings_amount': float(original_price - discounted_price),
            'savings_percentage': float((original_price - discounted_price) / original_price * 100),
            'valid_from': valid_from.isoformat(),
            'valid_until': valid_until.isoformat() if valid_until else None
        })


# ============================================================================
# INVENTORY COORDINATION EVENTS
# ============================================================================

class ProductInventoryRequiredEvent(DomainEvent):
    """Published when product needs inventory tracking setup"""
    
    def __init__(
        self,
        aggregate_id: str,
        sku: str,
        title: str,
        category: str,
        initial_stock: int = 0,
        warehouse_preference: Optional[str] = None,
        **kwargs
    ):
        super().__init__(aggregate_id, **kwargs)
        self.sku = sku
        self.title = title
        self.category = category
        self.initial_stock = initial_stock
        self.warehouse_preference = warehouse_preference
        
        self.event_data.update({
            'sku': sku,
            'title': title,
            'category': category,
            'initial_stock': initial_stock,
            'warehouse_preference': warehouse_preference,
            'requires_tracking': True
        })


class ProductStockLevelRequestedEvent(DomainEvent):
    """Published when product needs current stock level information"""
    
    def __init__(
        self,
        aggregate_id: str,
        sku: str,
        requested_by: str = "ecommerce_domain",
        **kwargs
    ):
        super().__init__(aggregate_id, **kwargs)
        self.sku = sku
        self.requested_by = requested_by
        
        self.event_data.update({
            'sku': sku,
            'requested_by': requested_by,
            'request_type': 'current_stock_level'
        })


class ProductStockReservationRequestedEvent(DomainEvent):
    """Published when stock needs to be reserved for order"""
    
    def __init__(
        self,
        aggregate_id: str,
        sku: str,
        quantity: int,
        order_id: str,
        customer_id: str,
        reservation_timeout_minutes: int = 15,
        **kwargs
    ):
        super().__init__(aggregate_id, **kwargs)
        self.sku = sku
        self.quantity = quantity
        self.order_id = order_id
        self.customer_id = customer_id
        self.reservation_timeout_minutes = reservation_timeout_minutes
        
        self.event_data.update({
            'sku': sku,
            'quantity': quantity,
            'order_id': order_id,
            'customer_id': customer_id,
            'reservation_timeout_minutes': reservation_timeout_minutes,
            'reservation_expires_at': (
                self.occurred_at + datetime.timedelta(minutes=reservation_timeout_minutes)
            ).isoformat()
        })


class ProductStockCommitmentRequestedEvent(DomainEvent):
    """Published when reserved stock needs to be committed (order confirmed)"""
    
    def __init__(
        self,
        aggregate_id: str,
        sku: str,
        quantity: int,
        order_id: str,
        reservation_id: Optional[str] = None,
        **kwargs
    ):
        super().__init__(aggregate_id, **kwargs)
        self.sku = sku
        self.quantity = quantity
        self.order_id = order_id
        self.reservation_id = reservation_id
        
        self.event_data.update({
            'sku': sku,
            'quantity': quantity,
            'order_id': order_id,
            'reservation_id': reservation_id,
            'action': 'commit_stock'
        })


class ProductStockReleaseRequestedEvent(DomainEvent):
    """Published when reserved stock needs to be released (order cancelled)"""
    
    def __init__(
        self,
        aggregate_id: str,
        sku: str,
        quantity: int,
        order_id: str,
        reservation_id: Optional[str] = None,
        reason: str = "",
        **kwargs
    ):
        super().__init__(aggregate_id, **kwargs)
        self.sku = sku
        self.quantity = quantity
        self.order_id = order_id
        self.reservation_id = reservation_id
        self.reason = reason
        
        self.event_data.update({
            'sku': sku,
            'quantity': quantity,
            'order_id': order_id,
            'reservation_id': reservation_id,
            'reason': reason,
            'action': 'release_stock'
        })


class ProductInventoryAlertEvent(DomainEvent):
    """Published when AI detects inventory issues"""
    
    def __init__(
        self,
        aggregate_id: str,
        sku: str,
        alert_type: str,  # 'LOW_STOCK', 'HIGH_STOCKOUT_RISK', 'OVERSTOCK'
        current_stock: int,
        risk_score: float,
        recommended_action: str,
        recommended_reorder_quantity: int = 0,
        **kwargs
    ):
        super().__init__(aggregate_id, **kwargs)
        self.sku = sku
        self.alert_type = alert_type
        self.current_stock = current_stock
        self.risk_score = risk_score
        self.recommended_action = recommended_action
        self.recommended_reorder_quantity = recommended_reorder_quantity
        
        self.event_data.update({
            'sku': sku,
            'alert_type': alert_type,
            'current_stock': current_stock,
            'risk_score': risk_score,
            'severity': self._determine_severity(),
            'recommended_action': recommended_action,
            'recommended_reorder_quantity': recommended_reorder_quantity
        })
    
    def _determine_severity(self) -> str:
        """Determine alert severity based on risk score"""
        if self.risk_score >= 90:
            return 'CRITICAL'
        elif self.risk_score >= 70:
            return 'HIGH'
        elif self.risk_score >= 40:
            return 'MEDIUM'
        else:
            return 'LOW'


# ============================================================================
# AI ANALYSIS EVENTS
# ============================================================================

class ProductAIAnalysisCompletedEvent(DomainEvent):
    """Published when AI analysis is completed"""
    
    def __init__(
        self,
        aggregate_id: str,
        sku: str,
        analysis_type: str,  # 'comprehensive', 'pricing', 'demand', etc.
        modules_analyzed: List[str],
        success_count: int,
        ai_confidence_score: float,
        alerts_generated: int,
        **kwargs
    ):
        super().__init__(aggregate_id, **kwargs)
        self.sku = sku
        self.analysis_type = analysis_type
        self.modules_analyzed = modules_analyzed
        self.success_count = success_count
        self.ai_confidence_score = ai_confidence_score
        self.alerts_generated = alerts_generated
        
        self.event_data.update({
            'sku': sku,
            'analysis_type': analysis_type,
            'modules_analyzed': modules_analyzed,
            'total_modules': len(modules_analyzed),
            'success_count': success_count,
            'success_rate': success_count / len(modules_analyzed) if modules_analyzed else 0,
            'ai_confidence_score': ai_confidence_score,
            'alerts_generated': alerts_generated
        })


class ProductAnalyticsUpdatedEvent(DomainEvent):
    """Published when product analytics are updated"""
    
    def __init__(
        self,
        aggregate_id: str,
        sku: str,
        analytics_type: str,  # 'performance', 'customer_behavior', 'sales'
        metrics_updated: Dict[str, Any],
        **kwargs
    ):
        super().__init__(aggregate_id, **kwargs)
        self.sku = sku
        self.analytics_type = analytics_type
        self.metrics_updated = metrics_updated
        
        self.event_data.update({
            'sku': sku,
            'analytics_type': analytics_type,
            'metrics_updated': metrics_updated
        })


class ProductRecommendationUpdatedEvent(DomainEvent):
    """Published when AI recommendations are updated"""
    
    def __init__(
        self,
        aggregate_id: str,
        sku: str,
        recommendation_count: int,
        cross_sell_score: float,
        upsell_count: int,
        **kwargs
    ):
        super().__init__(aggregate_id, **kwargs)
        self.sku = sku
        self.recommendation_count = recommendation_count
        self.cross_sell_score = cross_sell_score
        self.upsell_count = upsell_count
        
        self.event_data.update({
            'sku': sku,
            'recommendation_count': recommendation_count,
            'cross_sell_score': cross_sell_score,
            'upsell_count': upsell_count
        })


# ============================================================================
# PERFORMANCE AND SALES EVENTS
# ============================================================================

class ProductViewedEvent(DomainEvent):
    """Published when product is viewed by customer"""
    
    def __init__(
        self,
        aggregate_id: str,
        sku: str,
        customer_id: Optional[str] = None,
        session_id: Optional[str] = None,
        source: str = "web",  # web, mobile, api
        user_agent: Optional[str] = None,
        **kwargs
    ):
        super().__init__(aggregate_id, **kwargs)
        self.sku = sku
        self.customer_id = customer_id
        self.session_id = session_id
        self.source = source
        self.user_agent = user_agent
        
        self.event_data.update({
            'sku': sku,
            'customer_id': customer_id,
            'session_id': session_id,
            'source': source,
            'user_agent': user_agent,
            'is_authenticated': customer_id is not None
        })


class ProductSoldEvent(DomainEvent):
    """Published when product is sold"""
    
    def __init__(
        self,
        aggregate_id: str,
        sku: str,
        quantity: int,
        unit_price: Decimal,
        total_amount: Decimal,
        order_id: str,
        customer_id: str,
        **kwargs
    ):
        super().__init__(aggregate_id, **kwargs)
        self.sku = sku
        self.quantity = quantity
        self.unit_price = unit_price
        self.total_amount = total_amount
        self.order_id = order_id
        self.customer_id = customer_id
        
        self.event_data.update({
            'sku': sku,
            'quantity': quantity,
            'unit_price': float(unit_price),
            'total_amount': float(total_amount),
            'order_id': order_id,
            'customer_id': customer_id
        })


class ProductReturnedEvent(DomainEvent):
    """Published when product is returned"""
    
    def __init__(
        self,
        aggregate_id: str,
        sku: str,
        quantity: int,
        return_reason: str,
        order_id: str,
        customer_id: str,
        condition: str = "GOOD",  # GOOD, DAMAGED, DEFECTIVE
        **kwargs
    ):
        super().__init__(aggregate_id, **kwargs)
        self.sku = sku
        self.quantity = quantity
        self.return_reason = return_reason
        self.order_id = order_id
        self.customer_id = customer_id
        self.condition = condition
        
        self.event_data.update({
            'sku': sku,
            'quantity': quantity,
            'return_reason': return_reason,
            'order_id': order_id,
            'customer_id': customer_id,
            'condition': condition,
            'restockable': condition == 'GOOD'
        })


class ProductReviewedEvent(DomainEvent):
    """Published when product receives a review"""
    
    def __init__(
        self,
        aggregate_id: str,
        sku: str,
        customer_id: str,
        rating: int,
        review_text: Optional[str] = None,
        verified_purchase: bool = False,
        **kwargs
    ):
        super().__init__(aggregate_id, **kwargs)
        self.sku = sku
        self.customer_id = customer_id
        self.rating = rating
        self.review_text = review_text
        self.verified_purchase = verified_purchase
        
        self.event_data.update({
            'sku': sku,
            'customer_id': customer_id,
            'rating': rating,
            'has_review_text': review_text is not None,
            'verified_purchase': verified_purchase
        })


# ============================================================================
# CATALOG MANAGEMENT EVENTS
# ============================================================================

class ProductAddedToCollectionEvent(DomainEvent):
    """Published when product is added to collection"""
    
    def __init__(
        self,
        aggregate_id: str,
        sku: str,
        collection_name: str,
        is_featured: bool = False,
        **kwargs
    ):
        super().__init__(aggregate_id, **kwargs)
        self.sku = sku
        self.collection_name = collection_name
        self.is_featured = is_featured
        
        self.event_data.update({
            'sku': sku,
            'collection_name': collection_name,
            'is_featured': is_featured
        })


class ProductRemovedFromCollectionEvent(DomainEvent):
    """Published when product is removed from collection"""
    
    def __init__(
        self,
        aggregate_id: str,
        sku: str,
        collection_name: str,
        **kwargs
    ):
        super().__init__(aggregate_id, **kwargs)
        self.sku = sku
        self.collection_name = collection_name
        
        self.event_data.update({
            'sku': sku,
            'collection_name': collection_name
        })


class ProductFeaturedEvent(DomainEvent):
    """Published when product is marked as featured"""
    
    def __init__(
        self,
        aggregate_id: str,
        sku: str,
        featured_in: str = "homepage",  # homepage, category, collection
        **kwargs
    ):
        super().__init__(aggregate_id, **kwargs)
        self.sku = sku
        self.featured_in = featured_in
        
        self.event_data.update({
            'sku': sku,
            'featured_in': featured_in
        })


class ProductUnfeaturedEvent(DomainEvent):
    """Published when product is removed from featured"""
    
    def __init__(
        self,
        aggregate_id: str,
        sku: str,
        unfeatured_from: str = "homepage",
        **kwargs
    ):
        super().__init__(aggregate_id, **kwargs)
        self.sku = sku
        self.unfeatured_from = unfeatured_from
        
        self.event_data.update({
            'sku': sku,
            'unfeatured_from': unfeatured_from
        })