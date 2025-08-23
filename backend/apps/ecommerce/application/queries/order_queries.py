"""
Order Query Handlers
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime, timedelta

from ...domain.specifications.order_specifications import (
    UserOrdersSpecification, OrderStatusSpecification, 
    OrderDateRangeSpecification, PaidOrdersSpecification
)
from ...infrastructure.persistence.repositories.order_repository_impl import OrderRepositoryImpl
from ...infrastructure.persistence.repositories.product_repository_impl import ProductRepositoryImpl
from ..dto.order_dto import OrderResponseDTO, OrderItemResponseDTO
from .base import BaseQueryHandler


@dataclass
class OrderDetailQuery:
    """Query for order detail"""
    order_id: Optional[str] = None
    order_number: Optional[str] = None
    user_id: Optional[str] = None  # For access control
    include_tracking: bool = True
    include_items_details: bool = True
    include_payment_details: bool = False
    include_shipping_details: bool = True


@dataclass
class OrderListQuery:
    """Query for order list"""
    user_id: Optional[str] = None
    email: Optional[str] = None
    status: Optional[str] = None
    payment_status: Optional[str] = None
    fulfillment_status: Optional[str] = None
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    search: Optional[str] = None
    page: int = 1
    page_size: int = 20
    sort_by: str = 'created_at'
    sort_order: str = 'desc'


@dataclass
class OrderAnalyticsQuery:
    """Query for order analytics"""
    date_from: datetime
    date_to: datetime
    group_by: str = 'day'  # day, week, month
    user_id: Optional[str] = None
    include_items: bool = False
    include_trends: bool = True


@dataclass
class CustomerOrderHistoryQuery:
    """Query for customer order history"""
    user_id: str
    page: int = 1
    page_size: int = 10
    include_summary: bool = True
    include_favorites: bool = True
    status_filter: Optional[List[str]] = None


class OrderQueryHandler(BaseQueryHandler):
    """Handler for order queries"""
    
    def __init__(self, tenant):
        super().__init__(tenant)
        self.order_repository = OrderRepositoryImpl(tenant)
        self.product_repository = ProductRepositoryImpl(tenant)
    
    def handle_order_detail(self, query: OrderDetailQuery) -> Optional[OrderResponseDTO]:
        """Handle order detail query"""
        try:
            # Find order
            order = None
            
            if query.order_id:
                order = self.order_repository.find_by_id(query.order_id)
            elif query.order_number:
                order = self.order_repository.find_by_order_number(query.order_number)
            else:
                raise ValidationError("Order ID or order number required")
            
            if not order:
                return None
            
            # Validate access
            if query.user_id and str(order.user_id) != str(query.user_id):
                raise PermissionError("Access denied to order")
            
            # Build response DTO
            order_dto = OrderResponseDTO.from_entity(order)
            
            # Enrich with additional data
            if query.include_tracking:
                order_dto = self._enrich_with_tracking_info(order_dto)
            
            if query.include_items_details:
                order_dto = self._enrich_with_items_details(order_dto)
            
            if query.include_payment_details:
                order_dto = self._enrich_with_payment_details(order_dto)
            
            if query.include_shipping_details:
                order_dto = self._enrich_with_shipping_details(order_dto)
            
            return order_dto
            
        except Exception as e:
            self.log_error("Failed to fetch order detail", e, {
                'query': query.__dict__
            })
            raise
    
    def handle_order_list(self, query: OrderListQuery) -> Dict[str, Any]:
        """Handle order list query"""
        try:
            # Build specifications
            specs = []
            
            if query.user_id:
                specs.append(UserOrdersSpecification(query.user_id))
            
            if query.status:
                specs.append(OrderStatusSpecification(query.status))
            
            if query.date_from or query.date_to:
                specs.append(OrderDateRangeSpecification(query.date_from, query.date_to))
            
            # Build filters
            filters = {
                'specifications': specs,
                'page': query.page,
                'page_size': query.page_size,
                'sort_by': query.sort_by,
                'sort_order': query.sort_order
            }
            
            # Add additional filters
            if query.email:
                filters['email'] = query.email
            
            if query.payment_status:
                filters['payment_status'] = query.payment_status
            
            if query.fulfillment_status:
                filters['fulfillment_status'] = query.fulfillment_status
            
            if query.search:
                filters['search'] = query.search
            
            # Fetch orders
            result = self.order_repository.find_by_criteria(filters)
            
            # Transform to DTOs
            order_dtos = [
                OrderResponseDTO.from_entity(order) 
                for order in result['items']
            ]
            
            return {
                'orders': order_dtos,
                'total_count': result['total'],
                'page': query.page,
                'page_size': query.page_size,
                'has_next': result['has_next'],
                'has_previous': result['has_previous'],
                'summary': self._get_order_list_summary(result['items'])
            }
            
        except Exception as e:
            self.log_error("Failed to fetch order list", e)
            raise
    
    def handle_order_analytics(self, query: OrderAnalyticsQuery) -> Dict[str, Any]:
        """Handle order analytics query"""
        try:
            # Build date specifications
            specs = [OrderDateRangeSpecification(query.date_from, query.date_to)]
            
            if query.user_id:
                specs.append(UserOrdersSpecification(query.user_id))
            
            # Get orders for analysis
            orders = self.order_repository.find_by_criteria({
                'specifications': specs,
                'page_size': 10000,  # Get all orders for analytics
                'sort_by': 'created_at',
                'sort_order': 'asc'
            })['items']
            
            # Generate analytics
            analytics = {
                'period': {
                    'from': query.date_from,
                    'to': query.date_to,
                    'group_by': query.group_by
                },
                'summary': self._calculate_order_summary(orders),
                'time_series': self._generate_time_series(orders, query.group_by),
                'status_breakdown': self._get_status_breakdown(orders),
                'payment_breakdown': self._get_payment_breakdown(orders)
            }
            
            if query.include_items:
                analytics['item_analytics'] = self._get_item_analytics(orders)
            
            if query.include_trends:
                analytics['trends'] = self._calculate_trends(orders, query.group_by)
            
            return analytics
            
        except Exception as e:
            self.log_error("Failed to generate order analytics", e)
            raise
    
    def handle_customer_order_history(self, query: CustomerOrderHistoryQuery) -> Dict[str, Any]:
        """Handle customer order history query"""
        try:
            # Build specifications
            specs = [UserOrdersSpecification(query.user_id)]
            
            # Apply status filter
            filters = {
                'specifications': specs,
                'page': query.page,
                'page_size': query.page_size,
                'sort_by': 'created_at',
                'sort_order': 'desc'
            }
            
            if query.status_filter:
                filters['status__in'] = query.status_filter
            
            # Fetch orders
            result = self.order_repository.find_by_criteria(filters)
            
            # Transform to DTOs
            order_dtos = [
                OrderResponseDTO.from_entity(order) 
                for order in result['items']
            ]
            
            response = {
                'orders': order_dtos,
                'total_count': result['total'],
                'page': query.page,
                'page_size': query.page_size,
                'has_next': result['has_next'],
                'has_previous': result['has_previous']
            }
            
            # Add customer summary
            if query.include_summary:
                response['customer_summary'] = self._get_customer_summary(query.user_id)
            
            # Add favorite products
            if query.include_favorites:
                response['favorite_products'] = self._get_customer_favorites(query.user_id)
            
            return response
            
        except Exception as e:
            self.log_error("Failed to fetch customer order history", e)
            raise
    
    def _enrich_with_tracking_info(self, order_dto: OrderResponseDTO) -> OrderResponseDTO:
        """Enrich order with tracking information"""
        # This would integrate with shipping providers
        tracking_info = {
            'tracking_number': 'TRK123456789',
            'carrier': 'UPS',
            'status': 'in_transit',
            'estimated_delivery': '2024-01-15',
            'tracking_url': 'https://ups.com/track/TRK123456789',
            'tracking_history': [
                {
                    'date': '2024-01-10T10:00:00Z',
                    'status': 'shipped',
                    'location': 'Warehouse - New York',
                    'description': 'Package shipped'
                },
                {
                    'date': '2024-01-11T14:30:00Z',
                    'status': 'in_transit',
                    'location': 'Distribution Center - Chicago',
                    'description': 'Package in transit'
                }
            ]
        }
        
        order_dto.tracking_info = tracking_info
        return order_dto
    
    def _enrich_with_items_details(self, order_dto: OrderResponseDTO) -> OrderResponseDTO:
        """Enrich order items with product details"""
        enriched_items = []
        
        for item in order_dto.items:
            # Get product details
            product = self.product_repository.find_by_id(item.product_id)
            
            if product:
                enriched_item = OrderItemResponseDTO(
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
                    fulfillment_status=getattr(item, 'fulfillment_status', 'pending'),
                    can_return=self._can_return_item(order_dto, item),
                    can_review=self._can_review_item(order_dto, item)
                )
                enriched_items.append(enriched_item)
            else:
                enriched_items.append(item)
        
        order_dto.items = enriched_items
        return order_dto
    
    def _enrich_with_payment_details(self, order_dto: OrderResponseDTO) -> OrderResponseDTO:
        """Enrich order with payment details"""
        # This would integrate with payment providers
        payment_details = {
            'payment_method': 'Credit Card',
            'card_type': 'Visa',
            'last_four': '1234',
            'payment_processor': 'Stripe',
            'transaction_id': 'pi_1234567890',
            'payment_date': order_dto.created_at,
            'refunds': [],
            'can_refund': order_dto.payment_status == 'paid'
        }
        
        order_dto.payment_details = payment_details
        return order_dto
    
    def _enrich_with_shipping_details(self, order_dto: OrderResponseDTO) -> OrderResponseDTO:
        """Enrich order with shipping details"""
        shipping_details = {
            'shipping_method': 'Standard Shipping',
            'estimated_delivery': '2024-01-15',
            'shipping_cost': order_dto.shipping_cost,
            'packaging': 'Standard Box',
            'special_instructions': None,
            'signature_required': False
        }
        
        order_dto.shipping_details = shipping_details
        return order_dto
    
    def _get_order_list_summary(self, orders) -> Dict[str, Any]:
        """Get summary statistics for order list"""
        if not orders:
            return {}
        
        total_value = sum(float(order.total.amount) for order in orders)
        
        return {
            'total_orders': len(orders),
            'total_value': total_value,
            'average_order_value': total_value / len(orders),
            'status_counts': self._count_by_field(orders, 'status'),
            'payment_status_counts': self._count_by_field(orders, 'payment_status')
        }
    
    def _calculate_order_summary(self, orders) -> Dict[str, Any]:
        """Calculate order summary statistics"""
        if not orders:
            return {}
        
        total_revenue = sum(float(order.total.amount) for order in orders)
        paid_orders = [order for order in orders if order.payment_status == 'paid']
        
        return {
            'total_orders': len(orders),
            'total_revenue': total_revenue,
            'average_order_value': total_revenue / len(orders),
            'paid_orders': len(paid_orders),
            'conversion_rate': len(paid_orders) / len(orders) if orders else 0,
            'total_items_sold': sum(len(order.items) for order in orders)
        }
    
    def _generate_time_series(self, orders, group_by: str) -> List[Dict[str, Any]]:
        """Generate time series data for orders"""
        from collections import defaultdict
        
        time_series = defaultdict(lambda: {'orders': 0, 'revenue': 0})
        
        for order in orders:
            if group_by == 'day':
                key = order.created_at.date().isoformat()
            elif group_by == 'week':
                # Get start of week
                start_of_week = order.created_at.date() - timedelta(days=order.created_at.weekday())
                key = start_of_week.isoformat()
            elif group_by == 'month':
                key = order.created_at.strftime('%Y-%m')
            else:
                key = order.created_at.date().isoformat()
            
            time_series[key]['orders'] += 1
            time_series[key]['revenue'] += float(order.total.amount)
        
        # Convert to list and sort
        result = []
        for period, data in sorted(time_series.items()):
            result.append({
                'period': period,
                'orders': data['orders'],
                'revenue': data['revenue'],
                'average_order_value': data['revenue'] / data['orders']
            })
        
        return result
    
    def _get_status_breakdown(self, orders) -> Dict[str, int]:
        """Get breakdown of orders by status"""
        return self._count_by_field(orders, 'status')
    
    def _get_payment_breakdown(self, orders) -> Dict[str, int]:
        """Get breakdown of orders by payment status"""
        return self._count_by_field(orders, 'payment_status')
    
    def _get_item_analytics(self, orders) -> Dict[str, Any]:
        """Get analytics for order items"""
        from collections import defaultdict
        
        product_stats = defaultdict(lambda: {'quantity': 0, 'revenue': 0})
        
        for order in orders:
            for item in order.items:
                product_id = str(item.product_id)
                product_stats[product_id]['quantity'] += item.quantity
                product_stats[product_id]['revenue'] += float(item.total_price.amount)
        
        # Convert to list and sort by revenue
        top_products = []
        for product_id, stats in product_stats.items():
            top_products.append({
                'product_id': product_id,
                'quantity_sold': stats['quantity'],
                'revenue': stats['revenue']
            })
        
        top_products.sort(key=lambda x: x['revenue'], reverse=True)
        
        return {
            'top_products': top_products[:10],
            'total_products': len(product_stats),
            'total_items_sold': sum(stats['quantity'] for stats in product_stats.values())
        }
    
    def _calculate_trends(self, orders, group_by: str) -> Dict[str, Any]:
        """Calculate trends for orders"""
        time_series = self._generate_time_series(orders, group_by)
        
        if len(time_series) < 2:
            return {'trend': 'insufficient_data'}
        
        # Calculate simple trend
        recent_period = time_series[-1]
        previous_period = time_series[-2] if len(time_series) > 1 else time_series[0]
        
        order_trend = ((recent_period['orders'] - previous_period['orders']) / 
                      previous_period['orders'] * 100) if previous_period['orders'] > 0 else 0
        
        revenue_trend = ((recent_period['revenue'] - previous_period['revenue']) / 
                        previous_period['revenue'] * 100) if previous_period['revenue'] > 0 else 0
        
        return {
            'order_count_trend': round(order_trend, 2),
            'revenue_trend': round(revenue_trend, 2),
            'trend_direction': 'up' if order_trend > 5 else 'down' if order_trend < -5 else 'stable'
        }
    
    def _get_customer_summary(self, user_id: str) -> Dict[str, Any]:
        """Get customer order summary"""
        # Get all customer orders
        all_orders = self.order_repository.find_by_criteria({
            'specifications': [UserOrdersSpecification(user_id)],
            'page_size': 1000
        })['items']
        
        if not all_orders:
            return {}
        
        total_spent = sum(float(order.total.amount) for order in all_orders)
        paid_orders = [order for order in all_orders if order.payment_status == 'paid']
        
        return {
            'total_orders': len(all_orders),
            'total_spent': total_spent,
            'average_order_value': total_spent / len(all_orders),
            'lifetime_value': sum(float(order.total.amount) for order in paid_orders),
            'first_order_date': min(order.created_at for order in all_orders),
            'last_order_date': max(order.created_at for order in all_orders),
            'favorite_payment_method': self._get_most_common_field(all_orders, 'payment_method'),
            'order_frequency': self._calculate_order_frequency(all_orders)
        }
    
    def _get_customer_favorites(self, user_id: str) -> List[Dict[str, Any]]:
        """Get customer's favorite products based on order history"""
        from collections import defaultdict
        
        # Get recent orders
        recent_orders = self.order_repository.find_by_criteria({
            'specifications': [
                UserOrdersSpecification(user_id),
                OrderDateRangeSpecification(
                    datetime.now() - timedelta(days=365), 
                    datetime.now()
                )
            ],
            'page_size': 100
        })['items']
        
        # Count product purchases
        product_counts = defaultdict(int)
        for order in recent_orders:
            for item in order.items:
                product_counts[str(item.product_id)] += item.quantity
        
        # Get top products
        favorites = []
        for product_id, count in sorted(product_counts.items(), 
                                      key=lambda x: x[1], reverse=True)[:5]:
            product = self.product_repository.find_by_id(product_id)
            if product:
                favorites.append({
                    'product_id': product_id,
                    'title': product.title,
                    'purchase_count': count,
                    'last_purchased': max(
                        order.created_at for order in recent_orders
                        if any(str(item.product_id) == product_id for item in order.items)
                    )
                })
        
        return favorites
    
    def _can_return_item(self, order: OrderResponseDTO, item: OrderItemResponseDTO) -> bool:
        """Check if item can be returned"""
        # Business rules for returns
        return (
            order.status == 'delivered' and
            order.payment_status == 'paid' and
            (datetime.now() - order.created_at).days <= 30  # 30-day return policy
        )
    
    def _can_review_item(self, order: OrderResponseDTO, item: OrderItemResponseDTO) -> bool:
        """Check if item can be reviewed"""
        return (
            order.status in ['delivered', 'completed'] and
            order.payment_status == 'paid'
        )
    
    def _count_by_field(self, items, field: str) -> Dict[str, int]:
        """Count items by field value"""
        from collections import Counter
        return dict(Counter(getattr(item, field) for item in items))
    
    def _get_most_common_field(self, items, field: str) -> str:
        """Get most common value for field"""
        counts = self._count_by_field(items, field)
        return max(counts, key=counts.get) if counts else None
    
    def _calculate_order_frequency(self, orders) -> str:
        """Calculate customer order frequency"""
        if len(orders) < 2:
            return 'new_customer'
        
        # Calculate average days between orders
        sorted_orders = sorted(orders, key=lambda x: x.created_at)
        time_diffs = [
            (sorted_orders[i].created_at - sorted_orders[i-1].created_at).days
            for i in range(1, len(sorted_orders))
        ]
        
        avg_days = sum(time_diffs) / len(time_diffs)
        
        if avg_days <= 30:
            return 'frequent'  # Monthly or more
        elif avg_days <= 90:
            return 'regular'   # Quarterly
        elif avg_days <= 180:
            return 'occasional'  # Semi-annually
        else:
            return 'rare'      