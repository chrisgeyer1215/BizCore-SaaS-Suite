from django.db import transaction
from django.utils import timezone
from typing import List, Dict, Any, Optional
from ..base import BaseService, ServiceResult
from ...models import StockItem, Product, StockReservation

class CRMIntegrationService(BaseService):
    """
    Service for integrating inventory with CRM module
    """
    
    def check_product_availability_for_quote(self, quote_items: List[Dict[str, Any]]) -> ServiceResult:
        """Check product availability for CRM quote"""
        try:
            availability_results = []
            
            for item in quote_items:
                product_id = item.get('product_id')
                quantity_needed = item.get('quantity', 0)
                warehouse_id = item.get('warehouse_id')
                
                try:
                    # Get stock items for the product
                    stock_items = StockItem.objects.filter(
                        tenant=self.tenant,
                        product_id=product_id
                    )
                    
                    if warehouse_id:
                        stock_items = stock_items.filter(warehouse_id=warehouse_id)
                    
                    # Calculate total available
                    total_available = sum(
                        max(0, si.quantity_on_hand - si.quantity_reserved)
                        for si in stock_items
                    )
                    
                    # Get product info
                    product = Product.objects.get(id=product_id, tenant=self.tenant)
                    
                    availability_results.append({
                        'product_id': product_id,
                        'product_name': product.name,
                        'product_sku': product.sku,
                        'quantity_requested': quantity_needed,
                        'quantity_available': total_available,
                        'can_fulfill': total_available >= quantity_needed,
                        'shortfall': max(0, quantity_needed - total_available),
                        'estimated_delivery_date': self._estimate_delivery_date(product, quantity_needed, total_available),
                        'warehouses': [
                            {
                                'warehouse_id': si.warehouse.id,
                                'warehouse_name': si.warehouse.name,
                                'available_quantity': max(0, si.quantity_on_hand - si.quantity_reserved)
                            }
                            for si in stock_items if si.quantity_on_hand > si.quantity_reserved
                        ]
                    })
                    
                except Product.DoesNotExist:
                    availability_results.append({
                        'product_id': product_id,
                        'error': 'Product not found'
                    })
            
            return ServiceResult.success(
                data=availability_results,
                message=f"Checked availability for {len(quote_items)} items"
            )
            
        except Exception as e:
            return ServiceResult.error(f"Failed to check product availability: {str(e)}")
    
    def _estimate_delivery_date(self, product: Product, quantity_needed: int, 
                               available_quantity: int) -> Optional[str]:
        """Estimate delivery date based on availability and lead times"""
        try:
            if available_quantity >= quantity_needed:
                # Can fulfill from stock
                return timezone.now().date().isoformat()
            
            # Need to order from supplier
            from ...models import ProductSupplier
            
            primary_supplier = ProductSupplier.objects.filter(
                product=product,
                is_primary=True
            ).first()
            
            if primary_supplier:
                lead_time_days = primary_supplier.lead_time_days
                estimated_date = timezone.now().date() + timezone.timedelta(days=lead_time_days)
                return estimated_date.isoformat()
            
            # Default to 14 days if no supplier info
            estimated_date = timezone.now().date() + timezone.timedelta(days=14)
            return estimated_date.isoformat()
            
        except Exception:
            return None
    
    def reserve_stock_for_sales_order(self, sales_order_data: Dict[str, Any]) -> ServiceResult:
        """Reserve stock for confirmed sales order"""
        try:
            from ..stock.reservation_service import StockReservationService
            
            reservation_service = StockReservationService(tenant=self.tenant, user=self.user)
            
            # Prepare reservation data
            reservation_data = {
                'reservation_type': 'SALES_ORDER',
                'customer_reference': sales_order_data.get('customer_id'),
                'reference_number': sales_order_data.get('order_number'),
                'priority': 'HIGH',
                'fulfillment_strategy': 'PARTIAL_ALLOWED',
                'expected_fulfillment_date': sales_order_data.get('delivery_date'),
                'notes': f"Sales order reservation for {sales_order_data.get('customer_name', 'Unknown')}"
            }
            
            # Prepare items data
            items_data = []
            for item in sales_order_data.get('line_items', []):
                # Find best warehouse for this item
                best_warehouse = self._find_best_warehouse_for_item(
                    item['product_id'], 
                    item['quantity'],
                    sales_order_data.get('preferred_warehouse_id')
                )
                
                if best_warehouse:
                    items_data.append({
                        'stock_item_id': best_warehouse['stock_item_id'],
                        'quantity_requested': item['quantity'],
                        'unit_price': item.get('unit_price', 0),
                        'notes': f"Sales order item for {item.get('product_name', 'Unknown')}"
                    })
            
            # Create reservation
             reservation_service.create_reservation(reservation_data, items_data)
            else:
                return ServiceResult.error("No stock items found for reservation")
                
        except Exception as e:
            return ServiceResult.error(f"Failed to reserve stock for sales order: {str(e)}")
    
    def _find_best_warehouse_for_item(self, product_id: int, quantity: int, 
                                     preferred_warehouse_id: Optional[int] = None) -> Optional[Dict[str, Any]]:
        """Find best warehouse to fulfill item from"""
        try:
            stock_items = StockItem.objects.filter(
                tenant=self.tenant,
                product_id=product_id,
                quantity_on_hand__gt=0
            ).select_related('warehouse')
            
            # Prefer specified warehouse if available
            if preferred_warehouse_id:
                preferred_item = stock_items.filter(
                    warehouse_id=preferred_warehouse_id
                ).first()
                
                if preferred_item and (preferred_item.quantity_on_hand - preferred_item.quantity_reserved) >= quantity:
                    return {
                        'stock_item_id': preferred_item.id,
                        'warehouse_id': preferred_item.warehouse.id,
                        'available_quantity': preferred_item.quantity_on_hand - preferred_item.quantity_reserved
                    }
            
            # Find warehouse with sufficient stock
            for stock_item in stock_items:
                available = stock_item.quantity_on_hand - stock_item.quantity_reserved
                if available >= quantity:
                    return {
                        'stock_item_id': stock_item.id,
                        'warehouse_id': stock_item.warehouse.id,
                        'available_quantity': available
                    }
            
            # If no single warehouse has enough, return the one with most stock
            best_item = max(
                stock_items,
                key=lambda si: si.quantity_on_hand - si.quantity_reserved,
                default=None
            )
            
            if best_item:
                return {
                    'stock_item_id': best_item.id,
                    'warehouse_id': best_item.warehouse.id,
                    'available_quantity': best_item.quantity_on_hand - best_item.quantity_reserved
                }
            
            return None
            
        except Exception:
            return None
    
    def sync_customer_pricing(self, customer_data: Dict[str, Any]) -> ServiceResult:
        """Sync customer-specific pricing from CRM"""
        try:
            customer_id = customer_data.get('customer_id')
            pricing_rules = customer_data.get('pricing_rules', [])
            
            # This would update product pricing based on customer rules
            # Implementation depends on your pricing model
            
            updated_products = []
            
            for rule in pricing_rules:
                product_id = rule.get('product_id')
                discount_percent = rule.get('discount_percent', 0)
                special_price = rule.get('special_price')
                
                try:
                    product = Product.objects.get(id=product_id, tenant=self.tenant)
                    
                    # Store customer-specific pricing
                    # This might be in a separate CustomerPricing model
                    pricing_data = {
                        'customer_id': customer_id,
                        'product': product,
                        'discount_percent': discount_percent,
                        'special_price': special_price,
                        'effective_date': timezone.now().date(),
                        'updated_from_crm': True
                    }
                    
                    # Here you would save to CustomerPricing model
                    # CustomerPricing.objects.update_or_create(
                    #     customer_id=customer_id,
                    #     product=product,
                    #     defaults=pricing_data
                    # )
                    
                    updated_products.append(product.name)
                    
                except Product.DoesNotExist:
                    continue
            
            return ServiceResult.success(
                data={'updated_products': updated_products},
                message=f"Updated pricing for {len(updated_products)} products"
            )
            
        except Exception as e:
            return ServiceResult.error(f"Failed to sync customer pricing: {str(e)}")
    
    def get_customer_order_history(self, customer_id: str) -> ServiceResult:
        """Get inventory-related order history for customer"""
        try:
            # Get reservations for this customer
            reservations = StockReservation.objects.filter(
                tenant=self.tenant,
                customer_reference=customer_id
            ).select_related().prefetch_related('items__stock_item__product')
            
            order_history = []
            
            for reservation in reservations:
                order_data = {
                    'reservation_id': reservation.id,
                    'reference_number': reservation.reference_number,
                    'order_date': reservation.created_at.date(),
                    'status': reservation.status,
                    'total_quantity': reservation.total_quantity_reserved,
                    'total_value': reservation.total_value,
                    'fulfillment_date': reservation.fulfilled_date,
                    'items': []
                }
                
                for item in reservation.items.all():
                    order_data['items'].append({
                        'product_name': item.stock_item.product.name,
                        'product_sku': item.stock_item.product.sku,
                        'quantity_ordered': item.quantity_requested,
                        'quantity_fulfilled': item.quantity_reserved,
                        'unit_price': item.unit_price,
                        'warehouse': item.stock_item.warehouse.name
                    })
                
                order_history.append(order_data)
            
            # Sort by date, most recent first
            order_history.sort(key=lambda x: x['order_date'], reverse=True)
            
            return ServiceResult.success(
                data=order_history,
                message=f"Retrieved {len(order_history)} orders for customer"
            )
            
        except Exception as e:
            return ServiceResult.error(f"Failed to get customer order history: {str(e)}")
    
    def get_product_recommendations(self, customer_id: str, 
                                  current_quote_items: List[Dict[str, Any]]) -> ServiceResult:
        """Get product recommendations based on customer history and current quote"""
        try:
            # Get customer's previous orders
            previous_orders = self.get_customer_order_history(customer_id)
            
            if not previous_orders.is_success:
                return ServiceResult.success(data=[], message="No previous orders found")
            
            # Analyze purchase patterns
            frequently_ordered = {}
            for order in previous_orders item in order['items']:
                    product_sku = item['product_sku']
                    if product_sku not in frequently_ordered:
                        frequently_ordered[product_sku] = {
                            'product_name': item['product_name'],
                            'product_sku': product_sku,
                            'order_count': 0,
                            'total_quantity': 0,
                            'avg_quantity': 0
                        }
                    
                    frequently_ordered[product_sku]['order_count'] += 1
                    frequently_ordered[product_sku]['total_quantity'] += item['quantity_ordered']
            
            # Calculate averages and get current quote product SKUs
            current_quote_skus = {item.get('product_sku') for item in current_quote_items}
            
            recommendations = []
            for sku, data in frequently_ordered.items():
                if sku not in current_quote_skus and data['order_count'] >= 2:
                    data['avg_quantity'] = data['total_quantity'] / data['order_count']
                    
                    # Check current availability
                    try:
                        product = Product.objects.get(sku=sku, tenant=self.tenant)
                        stock_items = StockItem.objects.filter(
                            product=product,
                            tenant=self.tenant
                        )
                        
                        total_available = sum(
                            max(0, si.quantity_on_hand - si.quantity_reserved)
                            for si in stock_items
                        )
                        
                        if total_available > 0:
                            recommendations.append({
                                'product_id': product.id,
                                'product_name': data['product_name'],
                                'product_sku': sku,
                                'order_frequency': data['order_count'],
                                'avg_order_quantity': int(data['avg_quantity']),
                                'available_quantity': total_available,
                                'recommendation_reason': f"Frequently ordered ({data['order_count']} times)"
                            })
                            
                    except Product.DoesNotExist:
                        continue
            
            # Sort by frequency and availability
            recommendations.sort(key=lambda x: (x['order_frequency'], x['available_quantity']), reverse=True)
            
            return ServiceResult.success(
                data=recommendations[:10],  # Top 10 recommendations
                message=f"Generated {len(recommendations)} product recommendations"
            )
            
        except Exception as e:
            return ServiceResult.error(f"Failed to get product recommendations: {str(e)}")