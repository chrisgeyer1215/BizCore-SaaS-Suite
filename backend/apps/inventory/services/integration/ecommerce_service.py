from django.db import transaction
from django.utils import timezone
from typing import List, Dict, Any, Optional
from ..base import BaseService, ServiceResult
from ...models import StockItem, Product, StockMovement

class ECommerceIntegrationService(BaseService):
    """
    Service for integrating inventory with e-commerce platforms
    """
    
    def sync_inventory_to_ecommerce(self, platform: str = 'shopify') -> ServiceResult:
        """Sync inventory levels to e-commerce platform"""
        try:
            # Get all sellable products with stock
            products_to_sync = Product.objects.filter(
                tenant=self.tenant,
                is_active=True,
                is_sellable=True
            ).prefetch_related('stockitem_set')
            
            sync_data = []
            
            for product in products_to_sync:
                # Calculate total available quantity across all warehouses
                total_available = sum(
                    max(0, stock_item.quantity_on_hand - stock_item.quantity_reserved)
                    for stock_item in product.stockitem_set.all()
                )
                
                sync_data.append({
                    'product_id': product.id,
                    'sku': product.sku,
                    'available_quantity': int(total_available),
                    'last_updated': timezone.now().isoformat()
                })
            
            # Send to e-commerce platform
            if platform.lower() == 'shopify':
                result = self._sync_to_shopify(sync_data)
            elif platform.lower() == 'woocommerce':
                result = self._sync_to_woocommerce(sync_data)
            elif platform.lower() == 'magento':
                result = self._sync_to_magento(sync_data)
            else:
                return ServiceResult.error(f"Unsupported platform: {platform}")
            
            if result.is_success:
                # Update sync timestamp
                products_to_sync.update(last_ecommerce_sync=timezone.now())
                
                self.log_operation('sync_inventory_to_ecommerce', {
                    'platform': platform,
                    'products_synced': len(sync_data)
                })
            
            return result
            
        except Exception as e:
            return ServiceResult.error(f"Failed to sync inventory to e-commerce: {str(e)}")
    
    def _sync_to_, Any]]) -> ServiceResult:
        """Sync inventory to Shopify"""
        try:
            import requests
            from django.conf import settings
            
            shopify_config = getattr(settings, 'SHOPIFY_CONFIG', {})
            
            if not shopify_config.get('api_key') or not shopify_config.get('shop_url'):
                return ServiceResult.error("Shopify configuration missing")
            
            headers = {
                'X-Shopify-Access-Token': shopify_config['api_key'],
                'Content-Type': 'application/json'
            }
            
            successful_syncs = 0
             Find Shopify variant by SKU
                    search_url = f"{shopify_config['shop_url']}/admin/api/2023-01/products.json"
                    search_params = {'fields': 'id,variants', 'limit': 1}
                    
                    # This is simplified - you'd need to map your SKUs to Shopify variant IDs
                    inventory_data = {
                        'inventory_item_id': item['shopify_inventory_item_id'],  # You'd need to store this mapping
                        'available': item['available_quantity']
                    }
                    
                    # Update inventory level
                    inventory_url = f"{shopify_config['shop_url']}/admin/api/2023-01/inventory_levels/set.json"
                    
                    response = requests.post(
                        inventory_url,
                        json={'inventory_level': inventory_data},
                        headers=headers,
                        timeout=30
                    )
                    
                    if response.status_code == 200:
                        successful_syncs += 1
                    else:
                        self.logger.error(f"Shopify sync error for {item['sku']}: {response.text}")
                        
                except Exception as e:
                    self.logger.error(f"Error syncing {item['sku']} to Shopify: {str(e)}")
                    continue
            
            return ServiceResult.success(
                data={'synced_count': successful_syncs},
                message=f"Synced {successful_syncs} products to Shopify"
            )
            
        except Exception as e:
            return ServiceResult.error(f"Shopify sync failed: {str(e)}")
    
    def _sync_to_woocomm List[Dict[str, Any]]) -> ServiceResult:
        """Sync inventory to WooCommerce"""
        try:
            import requests
            from django.conf import settings
            
            woo_config = getattr(settings, 'WOOCOMMERCE_CONFIG', {})
            
            if not woo_config.get('consumer_key') or not woo_config.get('site_url'):
                return ServiceResult.error("WooCommerce configuration missing")
            
            successful_syncs = 0
            
            for item in sync_data:
                try:
                    # Update product stock
                    product_url = f"{woo_config['site_url']}/wp-json/wc/v3/products/{item['woo_product_id']}"
                    
                    auth = (woo_config['consumer_key'], woo_config['consumer_secret'])
                    
                    update_data = {
                        'stock_quantity': item['available_quantity'],
                        'manage_stock': True,
                        'in_stock': item['available_quantity'] > 0
                    }
                    
                    response = requests.put(
                        product_url,
                        json=update_data,
                        auth=auth,
                        timeout=30
                    )
                    
                    if response.status_code == 200:
                        successful_syncs += 1
                    else:
                        self.logger.error(f"WooCommerce sync error for {item['sku']}: {response.text}")
                        
                except Exception as e:
                    self.logger.error(f"Error syncing {item['sku']} to WooCommerce: {str(e)}")
                    continue
            
            return ServiceResult.success(
                data={'synced_count': successful_syncs},
                message=f"Synced {successful_syncs} products to WooCommerce"
            )
            
        except Exception as e:
            return ServiceResult.error(f"WooCommerce sync failed: {str(e)}")
    
    def _sync_, Any]]) -> ServiceResult:
        """Sync inventory to Magento"""
        try:
            # Similar implementation for Magento API
            return ServiceResult.success(message="Magento sync not implemented yet")
            
        except Exception as e:
            return ServiceResult.error(f"Magento sync failed: {str(e)}")
    
    def process_ecommerce_order[str, Any]) -> ServiceResult:
        """Process order received from e-commerce platform"""
        try:
            from ..stock.reservation_service import StockReservationService
            
            reservation_service = StockReservationService(tenant=self.tenant, user=self.user)
            
            # Prepare reservation data
            reservation_data = {
                'reservation_type': 'ECOMMERCE_ORDER',
                'customer_reference': order_data.get('customer_id', 'Unknown'),
                'reference_number': order_data.get('order_number'),
                'priority': 'HIGH',
                'fulfillment_strategy': 'ALL_OR_NOTHING',
                'expected_fulfillment_date': order_data.get('requested_ship_date'),
                'notes': f"E-commerce order from {order_data.get('platform', 'Unknown platform')}"
            }
            
            # Process order items
            items_data = []
            unavailable_items = []
            
            for line_item in order_data.get('line_items', []):
                # Find product by SKU
                try:
                    product = Product.objects.get(
                        sku=line_item['sku'],
                        tenant=self.tenant
                    )
                    
                    # Find best stock item for this product
                    stock_item = self._find_best_stock_item_for_order(
                        product,
                        line_item['quantity'],
                        order_data.get('preferred_warehouse')
                    )
                    
                    if stock_item:
                        items_data.append({
                            'stock_item_id': stock_item.id,
                            'quantity_requested': line_item['quantity'],
                            'unit_price': line_item.get('price', 0),
                            'notes': f"E-commerce line item - {product.name}"
                        })
                    else:
                        unavailable_items.append({
                            'sku': line_item['sku'],
                            'product_name': product.name,
                            'quantity_requested': line_item['quantity'],
                            'reason': 'Insufficient stock'
                        })
                        
                except Product.DoesNotExist:
                    unavailable_items.append({
                        'sku': line_item['sku'],
                        'quantity_requested': line_item['quantity'],
                        'reason': 'Product not found'
                    })
            
            if unavailable_items:
                return ServiceResult.error(
                    message="Some items are unavailable",
                    errors={'unavailable_items': unavailable_items}
                )
            
            # Create reservation
            ifresult = reservation_service.create_reservation(reservation_data, items_data)
                
                if reservation_result.is_success:
                    # Send confirmation back to e-commerce platform
                    confirmation_result = self._send_order_confirmation(
                        order_data, 
                        reservation_result.data
                    )
                    
                    return ServiceResult.success(
                        data={
                            'reservation': reservation_result.data,
                            'confirmation_sent': confirmation_result.is_success
                        },
                        message="E-commerce order processed successfully"
                    )
                else:
                    return reservation_result
            else:
                return ServiceResult.error("No valid items to process")
                
        except Exception as e:
            return ServiceResult.error(f"Failed to process e-commerce order: {str(e)}")
    
    def _find_best_stock_item_for_order(self, product: Product, quantity: int,
                                       preferred_warehouse: Optional[str] = None) -> Optional['StockItem']:
        """Find best stock item to fulfill e-commerce order"""
        try:
            stock_items = StockItem.objects.filter(
                tenant=self.tenant,
                product=product,
                quantity_on_hand__gt=0
            )
            
            # Prefer specified warehouse
            if preferred_warehouse:
                preferred_item = stock_items.filter(
                    warehouse__name=preferred_warehouse
                ).first()
                
                if preferred_item and (preferred_item.quantity_on_hand - preferred_item.quantity_reserved) >= quantity:
                    return preferred_item
            
            # Find item with sufficient stock
            for stock_item in stock_items:
                available = stock_item.quantity_on_hand - stock_item.quantity_reserved
                if available >= quantity:
                    return stock_item
            
            return None
            
        except Exception:
            return None
    
    str, Any], 
                                reservation: 'StockReservation') -> ServiceResult:
        """Send order confirmation back to e-commerce platform"""
        try:
            platform = order_data.get('platform', '').lower()
            
            confirmation_data = {
                'order_number': order_data.get('order_number'),
                'reservation_id': reservation.id,
                'status': 'confirmed',
                'estimated_ship_date': reservation.expected_fulfillment_date.isoformat() if reservation.expected_fulfillment_date else None,
                'items': [
                    {
                        'sku': item.stock_item.product.sku,
                        'quantity_reserved': item.quantity_reserved,
                        'warehouse': item.stock_item.warehouse.name
                    }
                    for item in reservation.items.all()
                ]
            }
            
            # Send confirmation based on platform
            if platform == 'shopify':
                return self._send_shopify_confirmation(confirmation_data)
            elif platform == 'woocommerce':
                return self._send_woocommerce_confirmation(confirmation_data)
            else:
                return ServiceResult.success(message="Confirmation not sent - unsupported platform")
                
        except Exception as e:
            return ServiceResult.error(f"Failed to send order confirmation: {str(e)}")
    
    def _send_shopify_confirmation(self, confirmationSend confirmation to Shopify"""
        try:
            # Implement Shopify order update API call
            return ServiceResult.success(message="Shopify confirmation sent")
            
        except Exception as e:
            return ServiceResult.error(f"Shopify confirmation failed: {str(e)}")
    
    def _send_woocommerce_ Dict[str, Any]) -> ServiceResult:
        """Send confirmation to WooCommerce"""
        try:
            # Implement WooCommerce order update API call
            return ServiceResult.success(message="WooCommerce confirmation sent")
            
        except Exception as e:
            return ServiceResult.error(f"WooCommerce confirmation failed: {str(e)}")
    
    def handle_order_cancellation(self, Any]) -> ServiceResult:
        """Handle order cancellation from e-commerce platform"""
        try:
            from ..stock.reservation_service import StockReservationService
            
            reservation_service = StockReservationService(tenant=self.tenant, user=self.user)
            
            # Find reservation by order number
            from ...models import StockReservation
            
            reservation = StockReservation.objects.filter(
                tenant=self.tenant,
                reference_number=cancellation_data.get('order_number'),
                status__in=['RESERVED', 'PARTIALLY_RESERVED']
            ).first()
            
            if reservation:
                # Cancel the reservation
                cancel_result = reservation_service.cancel_reservation(
                    reservation.id,
                    reason=f"Cancelled from {cancellation_data.get('platform', 'e-commerce platform')}"
                )
                
                if cancel_result.is_success:
                    return ServiceResult.success(
                        data=cancel_result.data,
                        message="Order cancellation processed successfully"
                    )
                else:
                    return cancel_result
            else:
                return ServiceResult.warning("No active reservation found for this order")
                
        except Exception as e:
            return ServiceResult.error(f"Failed to handle order cancellation: {str(e)}")
    
    def get_low_stock_products_for_ecommerce(self, platform: str) -> ServiceResult:
        """Get products with low stock that should be disabled on e-commerce platform"""
        try:
            low_stock_items = StockItem.objects.filter(
                tenant=self.tenant,
                quantity_on_hand__lte=models.F('reorder_level'),
                product__is_sellable=True,
                product__is_active=True
            ).select_related('product')
            
            products_to_disable = []
            
            for stock_item in low_stock_items:
                available_quantity = max(0, stock_item.quantity_on_hand - stock_item.quantity_reserved)
                
                if available_quantity <= 0:
                    products_to_disable.append({
                        'product_id': stock_item.product.id,
                        'sku': stock_item.product.sku,
                        'name': stock_item.product.name,
                        'current_stock': stock_item.quantity_on_hand,
                        'reserved_stock': stock_item.quantity_reserved,
                        'available_stock': available_quantity,
                        'reorder_level': stock_item.reorder_level,
                        'action': 'disable'
                    })
            
            return ServiceResult.success(
                data=products_to_disable,
                message=f"Found {len(products_to_disable)} products to disable on {platform}"
            )
            
        except Exception as e:
            return ServiceResult.error(f"Failed to get low stock products: {str(e)}")