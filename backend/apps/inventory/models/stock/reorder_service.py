from django.db import transaction
from django.utils import timezone
from decimal import Decimal
from typing import List, Dict, Any, Optional
from ..base import BaseService, ServiceResult
from ...models import (
    StockItem, Product, ProductSupplier, PurchaseOrder,
    InventoryAlert, AlertRule
)

class ReorderService(BaseService):
    """
    Service for managing reorder points and automatic reordering
    """
    
    def calculate_reorder_points(self, warehouse_id: Optional[int] = None) -> ServiceResult:
        """Calculate optimal reorder points based on usage patterns"""
        try:
            self.validate_tenant()
            
            queryset = StockItem.objects.filter(tenant=self.tenant)
            if warehouse_id:
                queryset = queryset.filter(warehouse_id=warehouse_id)
            
            updated_items = []
            
            for stock_item in queryset.select_related('product'):
                # Calculate based on different methods
                usage_based = self._calculate_usage_based_reorder_point(stock_item)
                lead_time_based = self._calculate_lead_time_based_reorder_point(stock_item)
                seasonal_adjusted = self._apply_seasonal_adjustments(stock_item, usage_based)
                
                # Use the most appropriate method
                new_reorder_point = max(usage_based, lead_time_based, seasonal_adjusted)
                
                if new_reorder_point != stock_item.reorder_level:
                    old_level = stock_item.reorder_level
                    stock_item.reorder_level = new_reorder_point
                    stock_item.reorder_point_updated_at = timezone.now()
                    stock_item.save(update_fields=['reorder_level', 'reorder_point_updated_at'])
                    
                    updated_items.append({
                        'stock_item': stock_item,
                        'old_reorder_point': old_level,
                        'new_reorder_point': new_reorder_point,
                        'calculation_method': 'usage_based'
                    })
            
            self.log_operation('calculate_reorder_points', {
                'warehouse_id': warehouse_id,
                'items_updated': len(updated_items)
            })
            
            return ServiceResult.success(
                data=updated_items,
                message=f"Updated reorder points for {len(updated_items)} items"
            )
            
        except Exception as e:
            return ServiceResult.error(f"Failed to calculate reorder points: {str(e)}")
    
    def _calculate_usage_based_reorder_point(self, stock_item: StockItem) -> Decimal:
        """Calculate reorder point based on historical usage"""
        try:
            # Get usage data for last 3 months
            from datetime import timedelta
            cutoff_date = timezone.now() - timedelta(days=90)
            
            # Get total issued quantity in period
            total_issued = stock_item.stockmovementitem_set.filter(
                movement__movement_type__in=['ISSUE', 'TRANSFER_OUT'],
                movement__created_at__gte=cutoff_date
            ).aggregate(
                total=models.Sum('quantity')
            )['total'] or 0
            
            if total_issued > 0:
                # Calculate daily usage
                daily_usage = total_issued / 90
                
                # Get lead time from primary supplier
                primary_supplier = ProductSupplier.objects.filter(
                    product=stock_item.product,
                    is_primary=True
                ).first()
                
                lead_time_days = primary_supplier.lead_time_days if primary_supplier else 14
                safety_stock_days = 7  # Safety buffer
                
                # Reorder point = (Daily usage × Lead time) + Safety stock
                reorder_point = daily_usage * (lead_time_days + safety_stock_days)
                
                return max(Decimal('1'), Decimal(str(reorder_point)).quantize(Decimal('1')))
            
            return Decimal('10')  # Default minimum
            
        except Exception as e:
            self.logger.error(f"Error calculating usage-based reorder point: {str(e)}")
            return Decimal('10')
    
    def _calculate_lead_time_based_reorder_point(self, stock_item: StockItem) -> Decimal:
        """Calculate reorder point based on lead time analysis"""
        try:
            # Get primary supplier lead time
            primary_supplier = ProductSupplier.objects.filter(
                product=stock_item.product,
                is_primary=True
            ).first()
            
            if not primary_supplier:
                return Decimal('10')
            
            lead_time_days = primary_supplier.lead_time_days
            
            # Calculate average daily consumption
            avg_daily_consumption = self._get_average_daily_consumption(stock_item)
            
            # Add safety margin (25% of lead time consumption)
            safety_margin = (avg_daily_consumption * lead_time_days) * Decimal('0.25')
            
            reorder_point = (avg_daily_consumption * lead_time_days) + safety_margin
            
            return max(Decimal('1'), reorder_point.quantize(Decimal('1')))
            
        except Exception as e:
            self.logger.error(f"Error calculating lead time based reorder point: {str(e)}")
            return Decimal('10')
    
    def _apply_seasonal_adjustments(self, stock_item: StockItem, base_reorder_point: Decimal) -> Decimal:
        """Apply seasonal adjustments to reorder point"""
        try:
            current_month = timezone.now().month
            
            # Define seasonal multipliers (this could be data-driven)
            seasonal_multipliers = {
                1: 0.8,   # January - lower demand
                2: 0.8,   # February
                3: 0.9,   # March
                4: 1.0,   # April
                5: 1.1,   # May
                6: 1.2,   # June - higher demand
                7: 1.3,   # July - peak season
                8: 1.3,   # August
                9: 1.2,   # September
                10: 1.1,  # October
                11: 1.4,  # November - holiday season
                12: 1.5,  # December - peak holiday
            }
            
            multiplier = seasonal_multipliers.get(current_month, 1.0)
            adjusted_point = base_reorder_point * Decimal(str(multiplier))
            
            return adjusted_point.quantize(Decimal('1'))
            
        except Exception as e:
            self.logger.error(f"Error applying seasonal adjustments: {str(e)}")
            return base_reorder_point
    
    def _get_average_daily_consumption(self, stock_item: StockItem) -> Decimal:
        """Get average daily consumption for a stock item"""
        try:
            from datetime import timedelta
            cutoff_date = timezone.now() - timedelta(days=30)
            
            total_consumed = stock_item.stockmovementitem_set.filter(
                movement__movement_type__in=['ISSUE', 'TRANSFER_OUT', 'PRODUCTION_CONSUMPTION'],
                movement__created_at__gte=cutoff_date
            ).aggregate(
                total=models.Sum('quantity')
            )['total'] or 0
            
            return Decimal(str(total_consumed / 30)) if total_consumed > 0 else Decimal('0.1')
            
        except Exception as e:
            return Decimal('0.1')
    
    def generate_reorder_suggestions(self, warehouse_id: Optional[int] = None) -> ServiceResult:
        """Generate reorder suggestions based on current stock levels"""
        try:
            suggestions = []
            
            # Get items below reorder level
            queryset = StockItem.objects.filter(
                tenant=self.tenant,
                quantity_on_hand__lte=models.F('reorder_level'),
                product__is_active=True,
                product__is_purchasable=True
            ).select_related('product', 'warehouse')
            
            if warehouse_id:
                queryset = queryset.filter(warehouse_id=warehouse_id)
            
            for stock_item in queryset:
                # Get supplier information
                primary_supplier = ProductSupplier.objects.filter(
                    product=stock_item.product,
                    is_primary=True
                ).first()
                
                if primary_supplier:
                    # Calculate suggested order quantity
                    suggested_qty = self._calculate_suggested_order_quantity(stock_item)
                    
                    suggestion = {
                        'stock_item': stock_item,
                        'product': stock_item.product,
                        'warehouse': stock_item.warehouse,
                        'current_stock': stock_item.quantity_on_hand,
                        'reorder_level': stock_item.reorder_level,
                        'suggested_quantity': suggested_qty,
                        'supplier': primary_supplier.supplier,
                        'unit_cost': primary_supplier.supplier_cost,
                        'total_cost': suggested_qty * primary_supplier.supplier_cost,
                        'lead_time_days': primary_supplier.lead_time_days,
                        'urgency': self._calculate_urgency(stock_item)
                    }
                    
                    suggestions.append(suggestion)
            
            # Sort by urgency
            suggestions.sort(key=lambda x: x['urgency'], reverse=True)
            
            return ServiceResult.success(
                data=suggestions,
                message=f"Generated {len(suggestions)} reorder suggestions"
            )
            
        except Exception as e:
            return ServiceResult.error(f"Failed to generate reorder suggestions: {str(e)}")
    
    def _calculate_suggested_order_quantity(self, stock_item: StockItem) -> Decimal:
        """Calculate optimal order quantity"""
        try:
            # Economic Order Quantity (EOQ) calculation
            annual_demand = self._estimate_annual_demand(stock_item)
            
            if annual_demand <= 0:
                # Fallback to maximum stock level
                return max(
                    stock_item.maximum_stock_level - stock_item.quantity_on_hand,
                    stock_item.reorder_quantity or Decimal('10')
                )
            
            # Get ordering cost and holding cost (these could be configured per product)
            ordering_cost = Decimal('50')  # Cost per order
            holding_cost_rate = Decimal('0.25')  # 25% of unit cost per year
            
            primary_supplier = ProductSupplier.objects.filter(
                product=stock_item.product,
                is_primary=True
            ).first()
            
            unit_cost = primary_supplier.supplier_cost if primary_supplier else stock_item.unit_cost
            holding_cost = unit_cost * holding_cost_rate
            
            # EOQ = sqrt((2 * D * S) / H)
            # D = annual demand, S = ordering cost, H = holding cost per unit
            import math
            eoq = math.sqrt((2 * float(annual_demand) * float(ordering_cost)) / float(holding_cost))
            
            # Consider current stock and maximum level
            suggested_qty = Decimal(str(eoq))
            
            # Adjust for current stock level
            if stock_item.maximum_stock_level > 0:
                max_order = stock_item.maximum_stock_level - stock_item.quantity_on_hand
                suggested_qty = min(suggested_qty, max_order)
            
            return max(Decimal('1'), suggested_qty.quantize(Decimal('1')))
            
        except Exception as e:
            self.logger.error(f"Error calculating suggested order quantity: {str(e)}")
            return Decimal('10')
    
    def _estimate_annual_demand(self, stock_item: StockItem) -> Decimal:
        """Estimate annual demand based on historical data"""
        try:
            from datetime import timedelta
            
            # Get data from last 90 days and extrapolate
            cutoff_date = timezone.now() - timedelta(days=90)
            
            total_consumed = stock_item.stockmovementitem_set.filter(
                movement__movement_type__in=['ISSUE', 'TRANSFER_OUT'],
                movement__created_at__gte=cutoff_date
            ).aggregate(
                total=models.Sum('quantity')
            )['total'] or 0
            
            # Extrapolate to annual (90 days to 365 days)
            annual_demand = (total_consumed / 90) * 365
            
            return Decimal(str(annual_demand))
            
        except Exception as e:
            return Decimal('0')
    
    def _calculate_urgency(self, stock_item: StockItem) -> int:
        """Calculate urgency score for reorder (1-10, 10 being most urgent)"""
        try:
            current_stock = stock_item.quantity_on_hand
            reorder_level = stock_item.reorder_level
            
            if current_stock <= 0:
                return 10  # Out of stock - critical
            elif current_stock <= reorder_level * Decimal('0.5'):
                return 8   # Very low stock
            elif current_stock <= reorder_level * Decimal('0.75'):
                return 6   # Low stock
            elif current_stock <= reorder_level:
                return 4   # At reorder level
            else:
                return 2   # Above reorder level
                
        except Exception as e:
            return 5
    
    @transaction.atomic
    def create_automatic_purchase_orders(self, suggestions: List[Dict[str, Any]]) -> ServiceResult:
        """Create purchase orders automatically from reorder suggestions"""
        try:
            from ..purchasing.order_service import PurchaseOrderService
            
            po_service = PurchaseOrderService(tenant=self.tenant, user=self.user)
            created_orders = []
            
            # Group suggestions by supplier and warehouse
            grouped_suggestions = {}
            for suggestion in suggestions:
                supplier_id = suggestion['supplier'].id
                warehouse_id = suggestion['warehouse'].id
                key = f"{supplier_id}_{warehouse_id}"
                
                if key not in grouped_suggestions:
                    grouped_suggestions[key] = {
                        'supplier': suggestion['supplier'],
                        'warehouse': suggestion['warehouse'],
                        'items': []
                    }
                
                grouped_suggestions[key]['items'].append(suggestion)
            
            # Create PO for each supplier-warehouse combination
            for group in grouped_suggestions.values():
                order_data = {
                    'supplier_id': group['supplier'].id,
                    'warehouse_id': group['warehouse'].id,
                    'order_date': timezone.now().date(),
                    'notes': 'Auto-generated from reorder suggestions',
                    'priority': 'MEDIUM'
                }
                
                items_data = []
                for item in group['items']:
                    items_data.append({
                        'product_id': item['product'].id,
                        'quantity_ordered': item['suggested_quantity'],
                        'unit_cost': item['unit_cost'],
                        'notes': f"Auto-reorder - Current: {item['current_stock']}"
                    })
                
                result = po_service.create_purchase_order(order_data, items_data)
                if result.is_success:
                    created_orders.append(result.data)
            
            self.log_operation('create_automatic_purchase_orders', {
                'orders_created': len(created_orders),
                'total_suggestions': len(suggestions)
            })
            
            return ServiceResult.success(
                data=created_orders,
                message=f"Created {len(created_orders)} automatic purchase orders"
            )
            
        except Exception as e:
            return ServiceResult.error(f"Failed to create automatic purchase orders: {str(e)}")
    
    def analyze_reorder_performance(self, warehouse_id: Optional[int] = None) -> ServiceResult:
        """Analyze reorder point performance and accuracy"""
        try:
            from datetime import timedelta
            
            analysis_period = timedelta(days=90)
            cutoff_date = timezone.now() - analysis_period
            
            queryset = StockItem.objects.filter(tenant=self.tenant)
            if warehouse_id:
                queryset = queryset.filter(warehouse_id=warehouse_id)
            
            analysis_results = []
            
            for stock_item in queryset:
                # Check how often we hit reorder point
                stockouts = stock_item.stockmovementitem_set.filter(
                    movement__created_at__gte=cutoff_date,
                    stock_item__quantity_on_hand__lte=0  # This is approximate
                ).count()
                
                # Calculate average time between reorders
                reorder_movements = stock_item.stockmovementitem_set.filter(
                    movement__movement_type='RECEIPT',
                    movement__created_at__gte=cutoff_date
                ).order_by('movement__created_at')
                
                avg_reorder_interval = None
                if reorder_movements.count() > 1:
                    first_order = reorder_movements.first()
                    last_order = reorder_movements.last()
                    interval = (last_order.movement.created_at - first_order.movement.created_at).days
                    avg_reorder_interval = interval / (reorder_movements.count() - 1)
                
                analysis_results.append({
                    'product': stock_item.product,
                    'warehouse': stock_item.warehouse,
                    'current_reorder_level': stock_item.reorder_level,
                    'stockout_incidents': stockouts,
                    'avg_reorder_interval_days': avg_reorder_interval,
                    'performance_score': self._calculate_performance_score(stockouts, avg_reorder_interval),
                    'recommendation': self._get_reorder_recommendation(stock_item, stockouts)
                })
            
            return ServiceResult.success(
                data=analysis_results,
                message=f"Analyzed reorder performance for {len(analysis_results)} items"
            )
            
        except Exception as e:
            return ServiceResult.error(f"Failed to analyze reorder performance: {str(e)}")
    
    def _calculate_performance_score(self, stockouts: int, avg_interval: Optional[float]) -> str:
        """Calculate performance score for reorder points"""
        if stockouts == 0:
            return "EXCELLENT"
        elif stockouts <= 2:
            return "GOOD"
        elif stockouts <= 5:
            return "FAIR"
        else:
            return "POOR"
    
    def _get_reorder_recommendation(self, stock_item: StockItem, stockouts: int) -> str:
        """Get recommendation for reorder point adjustment"""
        if stockouts > 3:
            return "INCREASE_REORDER_LEVEL"
        elif stockouts == 0 and stock_item.quantity_on_hand > stock_item.reorder_level * 2:
            return "DECREASE_REORDER_LEVEL"
        else:
            return "MAINTAIN_CURRENT_LEVEL"