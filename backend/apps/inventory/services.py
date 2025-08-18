"""
Inventory business logic services
"""

from decimal import Decimal
from django.db import transaction
from django.utils import timezone
from datetime import timedelta
from typing import List, Dict, Optional, Tuple
import logging

from .models import (
    Product, StockItem, StockMovement, Batch, PurchaseOrder, PurchaseOrderItem,
    StockReservation, StockReservationItem, InventoryAlert, InventorySettings
)

logger = logging.getLogger(__name__)


class InventoryService:
    """Core inventory management service"""
    
    def __init__(self, tenant):
        self.tenant = tenant
        self.settings = self._get_settings()
    
    def _get_settings(self):
        """Get inventory settings for tenant"""
        try:
            return InventorySettings.objects.get(tenant=self.tenant)
        except InventorySettings.DoesNotExist:
            return InventorySettings.objects.create(tenant=self.tenant)
    
    @transaction.atomic
    def receive_stock(self, product, warehouse, quantity, unit_cost, 
                     batch_number=None, expiry_date=None, location=None,
                     reference_type='', reference_id='', user=None):
        """Receive stock into warehouse"""
        try:
            # Get or create stock item
            stock_item, created = StockItem.objects.get_or_create(
                tenant=self.tenant,
                product=product,
                warehouse=warehouse,
                location=location,
                defaults={
                    'unit_cost': unit_cost,
                    'average_cost': unit_cost,
                    'last_cost': unit_cost
                }
            )
            
            # Handle batch tracking
            batch = None
            if product.is_batch_tracked and batch_number:
                batch, batch_created = Batch.objects.get_or_create(
                    tenant=self.tenant,
                    product=product,
                    batch_number=batch_number,
                    defaults={
                        'initial_quantity': quantity,
                        'current_quantity': quantity,
                        'unit_cost': unit_cost,
                        'total_cost': quantity * unit_cost,
                        'expiry_date': expiry_date
                    }
                )
                
                if not batch_created:
                    batch.current_quantity += quantity
                    batch.total_cost += (quantity * unit_cost)
                    batch.save()
                
                stock_item.batch = batch
            
            # Receive stock
            success = stock_item.receive_stock(
                quantity=quantity,
                unit_cost=unit_cost,
                reason=f'Stock Receipt - {reference_type} {reference_id}'
            )
            
            if success:
                # Check for low stock alerts resolution
                self._check_stock_alerts(product, warehouse)
                
                logger.info(f"Received {quantity} units of {product.sku} into {warehouse.code}")
                return True, stock_item
            
            return False, "Failed to receive stock"
            
        except Exception as e:
            logger.error(f"Error receiving stock: {str(e)}")
            return False, str(e)
    
    @transaction.atomic
    def issue_stock(self, product, warehouse, quantity, reason='', 
                   location=None, batch=None, user=None):
        """Issue stock from warehouse"""
        try:
            # Find stock items to issue from
            stock_items = StockItem.objects.filter(
                tenant=self.tenant,
                product=product,
                warehouse=warehouse,
                is_active=True,
                quantity_available__gt=0
            )
            
            if location:
                stock_items = stock_items.filter(location=location)
            if batch:
                stock_items = stock_items.filter(batch=batch)
            
            # Order by FIFO/LIFO based on settings
            if self.settings.valuation_method == 'FIFO':
                stock_items = stock_items.order_by('created_at')
            elif self.settings.valuation_method == 'LIFO':
                stock_items = stock_items.order_by('-created_at')
            
            remaining_qty = Decimal(str(quantity))
            issued_items = []
            
            for stock_item in stock_items:
                if remaining_qty <= 0:
                    break
                
                available = stock_item.quantity_available
                issue_qty = min(available, remaining_qty)
                
                # Issue from this stock item
                stock_item.quantity_on_hand -= issue_qty
                stock_item.quantity_available -= issue_qty
                stock_item.update_total_value()
                stock_item.save()
                
                # Create movement record
                movement = StockMovement.objects.create(
                    tenant=self.tenant,
                    stock_item=stock_item,
                    movement_type='OUT',
                    movement_reason='SALES_ORDER',
                    quantity=issue_qty,
                    unit_cost=stock_item.average_cost,
                    total_cost=issue_qty * stock_item.average_cost,
                    reason=reason,
                    performed_by=user,
                    stock_before=stock_item.quantity_on_hand + issue_qty,
                    stock_after=stock_item.quantity_on_hand
                )
                
                issued_items.append({
                    'stock_item': stock_item,
                    'quantity': issue_qty,
                    'movement': movement
                })
                
                remaining_qty -= issue_qty
            
            if remaining_qty > 0:
                return False, f"Insufficient stock available. Short by {remaining_qty}"
            
            # Check for low stock alerts
            self._check_stock_alerts(product, warehouse)
            
            logger.info(f"Issued {quantity} units of {product.sku} from {warehouse.code}")
            return True, issued_items
            
        except Exception as e:
            logger.error(f"Error issuing stock: {str(e)}")
            return False, str(e)
    
    def _check_stock_alerts(self, product, warehouse):
        """Check and create/resolve stock alerts"""
        try:
            stock_items = StockItem.objects.filter(
                tenant=self.tenant,
                product=product,
                warehouse=warehouse,
                is_active=True
            )
            
            total_available = sum(item.quantity_available for item in stock_items)
            
            # Check for low stock
            if total_available <= product.reorder_point:
                if total_available <= 0:
                    alert_type = 'OUT_OF_STOCK'
                    severity = 'CRITICAL'
                    title = f"Out of Stock: {product.name}"
                    message = f"Product {product.sku} is out of stock in {warehouse.name}"
                else:
                    alert_type = 'LOW_STOCK'
                    severity = 'HIGH'
                    title = f"Low Stock: {product.name}"
                    message = f"Product {product.sku} is below reorder point in {warehouse.name}. Available: {total_available}"
                
                # Create or update alert
                alert, created = InventoryAlert.objects.get_or_create(
                    tenant=self.tenant,
                    alert_type=alert_type,
                    product=product,
                    warehouse=warehouse,
                    status='ACTIVE',
                    defaults={
                        'severity': severity,
                        'title': title,
                        'message': message,
                        'details': {
                            'available_quantity': float(total_available),
                            'reorder_point': float(product.reorder_point),
                            'reorder_quantity': float(product.reorder_quantity)
                        }
                    }
                )
                
                if not created:
                    alert.message = message
                    alert.details['available_quantity'] = float(total_available)
                    alert.save()
            
            else:
                # Resolve existing low stock alerts
                InventoryAlert.objects.filter(
                    tenant=self.tenant,
                    alert_type__in=['LOW_STOCK', 'OUT_OF_STOCK'],
                    product=product,
                    warehouse=warehouse,
                    status='ACTIVE'
                ).update(
                    status='RESOLVED',
                    resolved_at=timezone.now(),
                    notes='Stock level restored above reorder point'
                )
        
        except Exception as e:
            logger.error(f"Error checking stock alerts: {str(e)}")


class ReservationService:
    """Stock reservation management service"""
    
    def __init__(self, tenant):
        self.tenant = tenant
    
    @transaction.atomic
    def create_reservation(self, products user=None):
        """Create stock reservation for multiple products"""
        try:
            # Create reservation header
            reservation = StockReservation.objects.create(
                tenant=self.tenant,
                reservation_type=reservation_data.get('reservation_type', 'SALES_ORDER'),
                reference_type=reservation_data.get('reference_type', ''),
                reference_id=reservation_data.get('reference_id', ''),
                reference_number=reservation_data.get('reference_number', ''),
                reserved_for_name=reservation_data.get('reserved_for_name', ''),
                required_date=reservation_data.get('required_date', timezone.now()),
                expiry_date=reservation_data.get('expiry_date', timezone.now() + timedelta(days=7)),
                reason=reservation_data.get('reason', ''),
                created_by=user
            )
            
            reservation_items = []
            faileproduct_id = item_data['product_id']
                quantity = Decimal(str(item_data['quantity']))
                warehouse_id = item_data.get('warehouse_id')
                
                try:
                    product = Product.objects.get(id=product_id, tenant=self.tenant)
                    
                    # Find available stock
                    stock_items = StockItem.objects.filter(
                        tenant=self.tenant,
                        product=product,
                        is_active=True,
                        quantity_available__gt=0
                    )
                    
                    if warehouse_id:
                        stock_items = stock_items.filter(warehouse_id=warehouse_id)
                    
                    # Reserve stock from available items
                    remaining_qty = quantity
                    
                    for stock_item in stock_items.order_by('created_at'):
                        if remaining_qty <= 0:
                            break
                        
                        available = stock_item.quantity_available
                        reserve_qty = min(available, remaining_qty)
                        
                        if reserve_qty > 0:
                            # Reserve stock
                            success = stock_item.reserve_stock(
                                reserve_qty, 
                                f"Reservation {reservation.reservation_number}"
                            )
                            
                            if success:
                                # Create reservation item
                                reservation_item = StockReservationItem.objects.create(
                                    tenant=self.tenant,
                                    reservation=reservation,
                                    product=product,
                                    stock_item=stock_item,
                                    warehouse=stock_item.warehouse,
                                    location=stock_item.location,
                                    batch=stock_item.batch,
                                    quantity_reserved=reserve_qty,
                                    unit=product.unit,
                                    unit_cost=stock_item.average_cost,
                                    total_value=reserve_qty * stock_item.average_cost
                                )
                                
                                reservation_items.append(reservation_item)
                                remaining_qty -= reserve_qty
                    
                    if remaining_qty > 0:
                        failed_items.append({
                            'product': product.name,
                            'sku': product.sku,
                            'requested': float(quantity),
                            'reserved': float(quantity - remaining_qty),
                            'shortage': float(remaining_qty)
                        })
                
                except Product.DoesNotExist:
                    failed_items.append({
                        'product_id': product_id,
                        'error': 'Product not found'
                    })
            
            return True, {
                'reservation': reservation,
                'reservation_items': reservation_items,
                'failed_items': failed_items
            }
            
        except Exception as e:
            logger.error(f"Error creating reservation: {str(e)}")
            return False, str(e)
    
    @transaction.atomic
    def fulfill_reservation(self, reservation_i[Dict], user=None):
        """Fulfill stock reservation"""
        try:
            reservation = StockReservation.objects.get(id=reservation_id, tenant=self.tenant)
            
            if reservation.status not in ['ACTIVE', 'PARTIAL_FULFILLED']:
                return False, "Reservation is not active"
            
            fulfilled_items = []
            
            _item_id = item_data['reservation_item_id']
                fulfill_qty = Decimal(str(item_data['quantity']))
                
                try:
                    reservation_item = reservation.items.get(id=reservation_item_id)
                    
                    if fulfill_qty > reservation_item.pending_quantity:
                        continue  # Skip invalid fulfillments
                    
                    # Allocate reserved stock
                    stock_item = reservation_item.stock_item
                    success = stock_item.allocate_stock(
                        fulfill_qty,
                        f"Fulfillment of reservation {reservation.reservation_number}"
                    )
                    
                    if success:
                        # Update reservation item
                        reservation_item.quantity_fulfilled += fulfill_qty
                        reservation_item.save()
                        
                        fulfilled_items.append(reservation_item)
                
                except StockReservationItem.DoesNotExist:
                    continue
            
            # Update reservation status
            total_reserved = sum(item.quantity_reserved for item in reservation.items.all())
            total_fulfilled = sum(item.quantity_fulfilled for item in reservation.items.all())
            
            if total_fulfilled >= total_reserved:
                reservation.status = 'FULFILLED'
                reservation.fulfilled_date = timezone.now()
                reservation.fulfilled_by = user
            elif total_fulfilled > 0:
                reservation.status = 'PARTIAL_FULFILLED'
            
            reservation.save()
            
            return True, {
                'reservation': reservation,
                'fulfilled_items': fulfilled_items
            }
            
        except StockReservation.DoesNotExist:
            return False, "Reservation not found"
        except Exception as e:
            logger.error(f"Error fulfilling reservation: {str(e)}")
            return False, str(e)


class PurchaseOrderService:
    """Purchase order management service"""
    
    def __init__(self, tenant):
        self.tenant = tenant
    
    @transaction.atomic
    def auto_generate_purchase_orders(self, user=None):
        """Auto-generate purchase orders for products below reorder point"""
        try:
            # Get products that need reordering
            products_to_order = Product.objects.filter(
                tenant=self.tenant,
                status='ACTIVE',
                is_purchasable=True,
                track_inventory=True
            ).annotate(
                total_available=models.Sum('stock_items__quantity_available')
            ).filter(
                total_available__lte=models.F('reorder_point')
            )
            
            # Group by preferred supplier
            supplier_products = {}
            
            for product in products_to_order:
                if product.preferred_supplier:
                    supplier = product.preferred_supplier
                    if supplier not in supplier_products:
                        supplier_products[supplier] = []
                    
                    # Calculate order quantity
                    current_stock = product.total_available or 0
                    order_qty = max(
                        product.reorder_quantity,
                        product.min_stock_level - current_stock
                    )
                    
                    # Get supplier pricing
                    supplier_item = product.supplier_items.filter(
                        supplier=supplier,
                        is_active=True
                    ).first()
                    
                    if supplier_item:
                        supplier_products[supplier].append({
                            'product': product,
                            'order_quantity': order_qty,
                            'supplier_item': supplier_item
                        })
            
            created_pos = []
            
            # Create purchase orders
            for supplier, products in supplier_products.items():
                if not products:
                    continue
                
                # Create PO
                po = PurchaseOrder.objects.create(
                    tenant=self.tenant,
                    supplier=supplier,
                    delivery_warehouse=Warehouse.objects.filter(
                        tenant=self.tenant,
                        is_default=True
                    ).first(),
                    required_date=timezone.now().date() + timedelta(days=7),
                    buyer=user,
                    status='DRAFT'
                )
                
                # Create PO items
                for product_data in products:
                    PurchaseOrderItem.objects.create(
                        tenant=self.tenant,
                        purchase_order=po,
                        product=product_data['product'],
                        quantity_ordered=product_data['order_quantity'],
                        unit=product_data['product'].unit,
                        unit_cost=product_data['supplier_item'].cost_price,
                        supplier_sku=product_data['supplier_item'].supplier_sku,
                        supplier_product_name=product_data['supplier_item'].supplier_product_name
                    )
                
                # Calculate totals
                po.calculate_totals()
                created_pos.append(po)
            
            return True, created_pos
            
        except Exception as e:
            logger.error(f"Error auto-generating purchase orders: {str(e)}")
            return False, str(e)


class AlertService:
    """Inventory alert management service"""
    
    def __init__(self, tenant):
        self.tenant = tenant
    
    def check_expiry_alerts(self):
        """Check for expiring batches and create alerts"""
        try:
            # Get batches expiring in next 30 days
            warning_date = timezone.now().date() + timedelta(days=30)
            
            expiring_batches = Batch.objects.filter(
                tenant=self.tenant,
                expiry_date__lte=warning_date,
                expiry_date__gt=timezone.now().date(),
                status='ACTIVE',
                current_quantity__gt=0
            )
            
            for batch in expiring_batches:
                days_until_expiry = (batch.expiry_date - timezone.now().date()).days
                
                if days_until_expiry <= 7:
                    severity = 'CRITICAL'
                elif days_until_expiry <= 15:
                    severity = 'HIGH'
                else:
                    severity = 'MEDIUM'
                
                # Create or update alert
                alert, created = InventoryAlert.objects.get_or_create(
                    tenant=self.tenant,
                    alert_type='EXPIRY_WARNING',
                    product=batch.product,
                    status='ACTIVE',
                    defaults={
                        'severity': severity,
                        'title': f'Batch Expiring: {batch.product.name}',
                        'message': f'Batch {batch.batch_number} expires in {days_until_expiry} days',
                        'details': {
                            'batch_number': batch.batch_number,
                            'expiry_date': batch.expiry_date.isoformat(),
                            'days_until_expiry': days_until_expiry,
                            'current_quantity': float(batch.current_quantity)
                        }
                    }
                )
            
            # Check for expired batches
            expired_batches = Batch.objects.filter(
                tenant=self.tenant,
                expiry_date__lt=timezone.now().date(),
                status='ACTIVE',
                current_quantity__gt=0
            )
            
            for batch in expired_batches:
                # Update batch status
                batch.status = 'EXPIRED'
                batch.save()
                
                # Create critical alert
                InventoryAlert.objects.get_or_create(
                    tenant=self.tenant,
                    alert_type='EXPIRED_STOCK',
                    product=batch.product,
                    status='ACTIVE',
                    defaults={
                        'severity': 'CRITICAL',
                        'title': f'Expired Stock: {batch.product.name}',
                        'message': f'Batch {batch.batch_number} has expired',
                        'details': {
                            'batch_number': batch.batch_number,
                            'expiry_date': batch.expiry_date.isoformat(),
                            'current_quantity': float(batch.current_quantity)
                        }
                    }
                )
                
        except Exception as e:
            logger.error(f"Error checking expiry alerts: {str(e)}")
    
    def check_cycle_count_alerts(self):
        """Check for overdue cycle counts"""
        try:
            overdue_items = StockItem.objects.filter(
                tenant=self.tenant,
                is_active=True,
                next_count_due__lt=timezone.now().date()
            )
            
            for item in overdue_items:
                InventoryAlert.objects.get_or_create(
                    tenant=self.tenant,
                    alert_type='CYCLE_COUNT_DUE',
                    product=item.product,
                    warehouse=item.warehouse,
                    stock_item=item,
                    status='ACTIVE',
                    defaults={
                        'severity': 'MEDIUM',
                        'title': f'Cycle Count Due: {item.product.name}',
                        'message': f'Stock item in {item.warehouse.name} is due for cycle count',
                        'details': {
                            'due_date': item.next_count_due.isoformat(),
                            'days_overdue': (timezone.now().date() - item.next_count_due).days
                        }
                    }
                )
                
        except Exception as e:
            logger.error(f"Error checking cycle count alerts: {str(e)}")
    
    def cleanup_resolved_alerts(self):
        """Clean up old resolved alerts"""
        try:
            # Delete resolved alerts older than 30 days
            cutoff_date = timezone.now() - timedelta(days=30)
            
            deleted_count = InventoryAlert.objects.filter(
                tenant=self.tenant,
                status='RESOLVED',
                resolved_at__lt=cutoff_date
            ).delete()[0]
            
            logger.info(f"Cleaned up {deleted_count} old resolved alerts")
            return deleted_count
            
        except Exception as e:
            logger.error(f"Error cleaning up alerts: {str(e)}")
            return 0


class AnalyticsService:
    """Inventory analytics and reporting service"""
    
    def __init__(self, tenant):
        self.tenant = tenant
    
    def calculate_abc_analysis(self):
        """Calculate ABC classification for products"""
        try:
            # Get products with their total stock value
            products = Product.objects.filter(
                tenant=self.tenant,
                status='ACTIVE'
            ).annotate(
                total_stock_value=models.Sum('stock_items__total_value')
            ).filter(
                total_stock_value__gt=0
            ).order_by('-total_stock_value')
            
            total_value = sum(p.total_stock_value for p in products)
            
            if total_value == 0:
                return
            
            cumulative_value = 0
            
            for product in products:
                cumulative_value += product.total_stock_value
                cumulative_percentage = (cumulative_value / total_value) * 100
                
                if cumulative_percentage <= 80:
                    abc_class = 'A'
                elif cumulative_percentage <= 95:
                    abc_class = 'B'
                else:
                    abc_class = 'C'
                
                # Update product ABC classification
                product.abc_classification = abc_class
                product.save(update_fields=['abc_classification'])
                
                # Update stock items
                StockItem.objects.filter(
                    product=product,
                    tenant=self.tenant
                ).update(abc_classification=abc_class)
                
        except Exception as e:
            logger.error(f"Error calculating ABC analysis: {str(e)}")
    
    def calculate_turnover_rates(self):
        """Calculate inventory turnover rates"""
        try:
            stock_items = StockItem.objects.filter(
                tenant=self.tenant,
                is_active=True
            )
            
            for stock_item in stock_items:
                stock_item.calculate_turnover_rate()
                
        except Exception as e:
            logger.error(f"Error calculating turnover rates: {str(e)}")
