"""
Cart Query Handlers
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass

from ...domain.specifications.cart_specifications import (
    ActiveCartSpecification, UserCartSpecification, SessionCartSpecification
)
from ...infrastructure.persistence.repositories.cart_repository_impl import CartRepositoryImpl
from ...infrastructure.persistence.repositories.product_repository_impl import ProductRepositoryImpl
from ..dto.cart_dto import CartResponseDTO, CartItemResponseDTO
from .base import BaseQueryHandler


@dataclass
class CartDetailQuery:
    """Query for cart detail"""
    cart_id: Optional[str] = None
    user_id: Optional[str] = None
    session_key: Optional[str] = None
    include_product_details: bool = True
    include_pricing_breakdown: bool = True
    include_shipping_options: bool = False


@dataclass
class CartHistoryQuery:
    """Query for cart history"""
    user_id: str
    page: int = 1
    page_size: int = 10
    include_converted: bool = True
    include_abandoned: bool = True


@dataclass
class AbandonedCartsQuery:
    """Query for abandoned carts"""
    hours_since_update: int = 24
    min_cart_value: Optional[float] = None
    page: int = 1
    page_size: int = 50
    include_guest_carts: bool = True


class CartQueryHandler(BaseQueryHandler):
    """Handler for cart queries"""
    
    def __init__(self, tenant):
        super().__init__(tenant)
        self.cart_repository = CartRepositoryImpl(tenant)
        self.product_repository = ProductRepositoryImpl(tenant)
    
    def handle_cart_detail(self, query: CartDetailQuery) -> Optional[CartResponseDTO]:
        """Handle cart detail query"""
        try:
            # Find cart by different criteria
            cart = None
            
            if query.cart_id:
                cart = self.cart_repository.find_by_id(query.cart_id)
            elif query.user_id:
                # Get user's active cart
                carts = self.cart_repository.find_by_criteria({
                    'user_id': query.user_id,
                    'specifications': [ActiveCartSpecification()]
                })
                cart = carts[0] if carts else None
            elif query.session_key:
                # Get session cart
                carts = self.cart_repository.find_by_criteria({
                    'session_key': query.session_key,
                    'specifications': [ActiveCartSpecification()]
                })
                cart = carts[0] if carts else None
            
            if not cart:
                return None
            
            # Build response DTO
            cart_dto = CartResponseDTO.from_entity(cart)
            
            # Enrich with additional data if requested
            if query.include_product_details:
                cart_dto = self._enrich_with_product_details(cart_dto)
            
            if query.include_pricing_breakdown:
                cart_dto = self._enrich_with_pricing_breakdown(cart_dto)
            
            if query.include_shipping_options:
                cart_dto = self._enrich_with_shipping_options(cart_dto)
            
            return cart_dto
            
        except Exception as e:
            self.log_error("Failed to fetch cart detail", e, {
                'query': query.__dict__
            })
            raise
    
    def handle_cart_history(self, query: CartHistoryQuery) -> Dict[str, Any]:
        """Handle cart history query"""
        try:
            # Build specifications
            specs = [UserCartSpecification(query.user_id)]
            
            # Apply filters
            filters = {
                'specifications': specs,
                'page': query.page,
                'page_size': query.page_size,
                'sort_by': 'updated_at',
                'sort_order': 'desc'
            }
            
            if not query.include_converted:
                filters['exclude_status'] = ['converted']
            
            if not query.include_abandoned:
                filters['exclude_status'] = filters.get('exclude_status', []) + ['abandoned']
            
            # Fetch carts
            result = self.cart_repository.find_by_criteria(filters)
            
            # Transform to DTOs
            cart_dtos = [
                CartResponseDTO.from_entity(cart) 
                for cart in result['items']
            ]
            
            return {
                'carts': cart_dtos,
                'total_count': result['total'],
                'page': query.page,
                'page_size': query.page_size,
                'has_next': result['has_next'],
                'has_previous': result['has_previous'],
                'summary': self._get_cart_history_summary(query.user_id)
            }
            
        except Exception as e:
            self.log_error("Failed to fetch cart history", e)
            raise
    
    def handle_abandoned_carts(self, query: AbandonedCartsQuery) -> Dict[str, Any]:
        """Handle abandoned carts query"""
        try:
            from datetime import datetime, timedelta
            
            # Calculate cutoff time
            cutoff_time = datetime.now() - timedelta(hours=query.hours_since_update)
            
            # Build filters
            filters = {
                'updated_before': cutoff_time,
                'status': 'active',
                'page': query.page,
                'page_size': query.page_size,
                'sort_by': 'updated_at',
                'sort_order': 'asc'  # Oldest first
            }
            
            if query.min_cart_value:
                filters['min_total'] = query.min_cart_value
            
            if not query.include_guest_carts:
                filters['user_id__isnull'] = False
            
            # Fetch abandoned carts
            result = self.cart_repository.find_by_criteria(filters)
            
            # Transform to DTOs with abandonment info
            cart_dtos = []
            for cart in result['items']:
                cart_dto = CartResponseDTO.from_entity(cart)
                cart_dto = self._enrich_with_abandonment_info(cart_dto, cutoff_time)
                cart_dtos.append(cart_dto)
            
            return {
                'abandoned_carts': cart_dtos,
                'total_count': result['total'],
                'page': query.page,
                'page_size': query.page_size,
                'has_next': result['has_next'],
                'has_previous': result['has_previous'],
                'summary': {
                    'total_abandoned_value': sum(cart.total for cart in cart_dtos),
                    'average_cart_value': sum(cart.total for cart in cart_dtos) / len(cart_dtos) if cart_dtos else 0,
                    'recovery_opportunities': len([cart for cart in cart_dtos if cart.total > (query.min_cart_value or 0)])
                }
            }
            
        except Exception as e:
            self.log_error("Failed to fetch abandoned carts", e)
            raise
    
    def _enrich_with_product_details(self, cart_dto: CartResponseDTO) -> CartResponseDTO:
        """Enrich cart with detailed product information"""
        enriched_items = []
        
        for item in cart_dto.items:
            # Get product details
            product = self.product_repository.find_by_id(item.product_id)
            
            if product:
                # Create enriched item DTO
                enriched_item = CartItemResponseDTO(
                    id=item.id,
                    product_id=item.product_id,
                    product_title=product.title,
                    product_sku=str(product.sku),
                    product_brand=product.brand,
                    product_image=product.featured_image_url if hasattr(product, 'featured_image_url') else None,
                    product_url=product.get_absolute_url() if hasattr(product, 'get_absolute_url') else None,
                    variant_id=item.variant_id,
                    variant_title=item.variant_title,
                    quantity=item.quantity,
                    unit_price=item.unit_price,
                    total_price=item.total_price,
                    currency=item.currency,
                    custom_attributes=item.custom_attributes,
                    availability=self._get_item_availability(product, item.variant_id, item.quantity),
                    price_changes=self._check_price_changes(product, item.variant_id, item.unit_price)
                )
                enriched_items.append(enriched_item)
            else:
                # Product not found - mark as unavailable
                enriched_item = item.__dict__.copy()
                enriched_item['availability'] = {
                    'available': False,
                    'reason': 'Product no longer available'
                }
                enriched_items.append(CartItemResponseDTO(**enriched_item))
        
        # Update cart DTO
        cart_dto.items = enriched_items
        return cart_dto
    
    def _enrich_with_pricing_breakdown(self, cart_dto: CartResponseDTO) -> CartResponseDTO:
        """Enrich cart with detailed pricing breakdown"""
        # Add pricing breakdown
        pricing_breakdown = {
            'subtotal': cart_dto.subtotal,
            'shipping_cost': cart_dto.shipping_cost,
            'tax_breakdown': self._get_tax_breakdown(cart_dto),
            'discount_breakdown': self._get_discount_breakdown(cart_dto),
            'total': cart_dto.total,
            'savings': cart_dto.discount_amount,
            'currency': cart_dto.currency
        }
        
        cart_dto.pricing_breakdown = pricing_breakdown
        return cart_dto
    
    def _enrich_with_shipping_options(self, cart_dto: CartResponseDTO) -> CartResponseDTO:
        """Enrich cart with available shipping options"""
        # This would integrate with shipping service
        shipping_options = [
            {
                'id': 'standard',
                'name': 'Standard Shipping',
                'description': '5-7 business days',
                'cost': 5.99,
                'estimated_delivery': '2024-01-15'
            },
            {
                'id': 'express',
                'name': 'Express Shipping',
                'description': '2-3 business days',
                'cost': 12.99,
                'estimated_delivery': '2024-01-10'
            },
            {
                'id': 'overnight',
                'name': 'Overnight Shipping',
                'description': 'Next business day',
                'cost': 24.99,
                'estimated_delivery': '2024-01-08'
            }
        ]
        
        cart_dto.shipping_options = shipping_options
        return cart_dto
    
    def _get_item_availability(self, product, variant_id: Optional[str], quantity: int) -> Dict[str, Any]:
        """Check item availability"""
        if variant_id:
            variant = product.get_variant(variant_id)
            if not variant:
                return {'available': False, 'reason': 'Variant not found'}
            
            if not variant.is_active:
                return {'available': False, 'reason': 'Variant no longer available'}
            
            if variant.track_quantity and variant.stock_quantity < quantity:
                return {
                    'available': False,
                    'reason': f'Only {variant.stock_quantity} available',
                    'available_quantity': variant.stock_quantity
                }
        else:
            if not product.is_active or not product.is_published:
                return {'available': False, 'reason': 'Product no longer available'}
            
            if product.track_quantity and product.stock_quantity < quantity:
                return {
                    'available': False,
                    'reason': f'Only {product.stock_quantity} available',
                    'available_quantity': product.stock_quantity
                }
        
        return {'available': True}
    
    def _check_price_changes(self, product, variant_id: Optional[str], current_price: float) -> Dict[str, Any]:
        """Check if prices have changed since item was added"""
        if variant_id:
            variant = product.get_variant(variant_id)
            current_product_price = float(variant.price.amount) if variant and variant.price else float(product.price.amount)
        else:
            current_product_price = float(product.price.amount)
        
        if abs(current_product_price - current_price) > 0.01:  # Price changed
            return {
                'changed': True,
                'old_price': current_price,
                'new_price': current_product_price,
                'difference': current_product_price - current_price
            }
        
        return {'changed': False}
    
    def _get_tax_breakdown(self, cart_dto: CartResponseDTO) -> Dict[str, Any]:
        """Get detailed tax breakdown"""
        # This would integrate with tax service
        return {
            'total_tax': cart_dto.tax_amount,
            'tax_rate': 0.08,  # 8%
            'tax_details': [
                {
                    'type': 'Sales Tax',
                    'rate': 0.08,
                    'amount': cart_dto.tax_amount
                }
            ]
        }
    
    def _get_discount_breakdown(self, cart_dto: CartResponseDTO) -> List[Dict[str, Any]]:
        """Get detailed discount breakdown"""
        # This would show applied coupons, promotions, etc.
        discounts = []
        
        if cart_dto.discount_amount > 0:
            discounts.append({
                'type': 'Coupon',
                'name': 'SAVE10',
                'description': '10% off entire order',
                'amount': cart_dto.discount_amount
            })
        
        return discounts
    
    def _get_cart_history_summary(self, user_id: str) -> Dict[str, Any]:
        """Get cart history summary for user"""
        # This would aggregate cart statistics
        return {
            'total_carts': 5,
            'converted_carts': 3,
            'abandoned_carts': 2,
            'conversion_rate': 0.6,
            'average_cart_value': 75.50,
            'total_spent': 226.50
        }
    
    def _enrich_with_abandonment_info(self, cart_dto: CartResponseDTO, cutoff_time) -> CartResponseDTO:
        """Enrich cart with abandonment information"""
        hours_abandoned = (cutoff_time - cart_dto.updated_at).total_seconds() / 3600
        
        cart_dto.abandonment_info = {
            'hours_abandoned': round(hours_abandoned, 1),
            'recovery_probability': self._calculate_recovery_probability(hours_abandoned, cart_dto.total),
            'recommended_discount': self._recommend_recovery_discount(cart_dto.total),
            'last_viewed_items': self._get_last_viewed_items(cart_dto)
        }
        
        return cart_dto
    
    def _calculate_recovery_probability(self, hours_abandoned: float, cart_value: float) -> float:
        """Calculate probability of cart recovery"""
        # Simple heuristic - would be ML model in production
        base_probability = 0.3
        
        # Decrease probability over time
        time_factor = max(0.1, 1 - (hours_abandoned / 168))  # 168 hours = 1 week
        
        # Increase probability for higher value carts
        value_factor = min(1.5, 1 + (cart_value / 1000))
        
        return min(0.9, base_probability * time_factor * value_factor)
    
    def _recommend_recovery_discount(self, cart_value: float) -> Dict[str, Any]:
        """Recommend discount for cart recovery"""
        if cart_value > 200:
            return {'type': 'percentage', 'value': 15, 'description': '15% off your order'}
        elif cart_value > 100:
            return {'type': 'percentage', 'value': 10, 'description': '10% off your order'}
        else:
            return {'type': 'fixed', 'value': 5, 'description': '$5 off your order'}
    
    def _get_last_viewed_items(self, cart_dto: CartResponseDTO) -> List[str]:
        """Get last viewed items for recovery emails"""
        # Return product IDs of most recently added items
        return [item.product_id for item in cart_dto.items[-3:]]  