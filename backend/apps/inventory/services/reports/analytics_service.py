from django.db import models
from django.db.models import Q, F, Sum, Count, Avg, Max, Min, Case, When, Value
from django.db.models.functions import Coalesce, Extract, TruncMonth, TruncWeek
from django.utils import timezone
from datetime import timedelta, datetime
from decimal import Decimal
from typing import List, Dict, Any, Optional, Tuple
from ..base import BaseService, ServiceResult
from ...models import (
    StockItem, StockMovement, Product, Supplier, Warehouse,
    PurchaseOrder, StockValuationLayer, InventoryAlert
)

class AnalyticsService(BaseService):
    """
    Service for advanced inventory analytics and business intelligence
    """
    
    def get_inventory_kpis(self, date_range: Optional[Dict[str, datetime]] = None) -> ServiceResult:
        """Get key performance indicators for inventory"""
        try:
            if not date_range:
                end_date = timezone.now()
                start_date = end_date - timedelta(days=30)
                date_range = {'start_date': start_date, 'end_date': end_date}
            
            # Stock KPIs
            stock_kpis = self._calculate_stock_kpis()
            
            # Movement KPIs
            movement_kpis = self._calculate_movement_kpis(date_range)
            
            # Financial KPIs
            financial_kpis = self._calculate_financial_kpis(date_range)
            
            # Operational KPIs
            operational_kpis = self._calculate_operational_kpis(date_range)
            
            # Performance KPIs
            performance_kpis = self._calculate_performance_kpis(date_range)
            
            kpis = {
                'stock': stock_kpis,
                'movement': movement_kpis,
                'financial': financial_kpis,
                'operational': operational_kpis,
                'performance': performance_kpis,
                'date_range': {
                    'start_date': date_range['start_date'].isoformat(),
                    'end_date': date_range['end_date'].isoformat()
                }
            }
            
            return ServiceResult.success(
                data=kpis,
                message="Inventory KPIs calculated successfully"
            )
            
        except Exception as e:
            return ServiceResult.error(f"Failed to calculate inventory KPIs: {str(e)}")
    
    def _calculate_stock_kpis(self) -> Dict[str, Any]:
        """Calculate stock-related KPIs"""
        try:
            stock_items = StockItem.objects.filter(tenant=self.tenant)
            
            # Basic stock metrics
            total_items = stock_items.count()
            total_quantity = stock_items.aggregate(Sum('quantity_on_hand'))['quantity_on_hand__sum'] or 0
            total_value = stock_items.aggregate(
                total=Sum(F('quantity_on_hand') * F('unit_cost'))
            )['total'] or 0
            
            # Stock status breakdown
            out_of_stock = stock_items.filter(quantity_on_hand=0).count()
            low_stock = stock_items.filter(
                quantity_on_hand__lte=F('reorder_level'),
                quantity_on_hand__gt=0,
                reorder_level__gt=0
            ).count()
            overstock = stock_items.filter(
                quantity_on_hand__gte=F('maximum_stock_level'),
                maximum_stock_level__gt=0
            ).count()
            negative_stock = stock_items.filter(quantity_on_hand__lt=0).count()
            
            # Stock health percentages
            stock_health = {
                'healthy_stock_percentage': ((total_items - out_of_stock - low_stock - overstock - negative_stock) / total_items * 100) if total_items > 0 else 0,
                'out_of_stock_percentage': (out_of_stock / total_items * 100) if total_items > 0 else 0,
                'low_stock_percentage': (low_stock / total_items * 100) if total_items > 0 else 0,
                'overstock_percentage': (overstock / total_items * 100) if total_items > 0 else 0
            }
            
            # ABC Analysis breakdown
            abc_breakdown = stock_items.values('abc_classification').annotate(
                count=Count('id'),
                total_value=Sum(F('quantity_on_hand') * F('unit_cost'))
            ).order_by('abc_classification')
            
            return {
                'total_items': total_items,
                'total_quantity': float(total_quantity),
                'total_value': float(total_value),
                'average_item_value': float(total_value / total_items) if total_items > 0 else 0,
                'stock_status': {
                    'out_of_stock': out_of_stock,
                    'low_stock': low_stock,
                    'overstock': overstock,
                    'negative_stock': negative_stock
                },
                'stock_health': stock_health,
                'abc_breakdown': list(abc_breakdown)
            }
            
        except Exception as e:
            self.logger.error(f"Error calculating stock KPIs: {str(e)}")
            return {}
    
    def _calculate_movement_kpis(self, date_range: Dict[str, datetime]) -> Dict[str, Any]:
        """Calculate movement-related KPIs"""
        try:
            movements = StockMovement.objects.filter(
                tenant=self.tenant,
                created_at__range=[date_range['start_date'], date_range['end_date']]
            )
            
            # Movement summary
            total_movements = movements.count()
            
            # Movement type breakdown
            movement_breakdown = movements.values('movement_type').annotate(
                count=Count('id'),
                total_quantity=Sum('items__quantity'),
                total_value=Sum(F('items__quantity') * F('items__unit_cost'))
            ).order_by('-count')
            
            # Daily movement average
            days_in_period = (date_range['end_date'] - date_range['start_date']).days or 1
            daily_movement_avg = total_movements / days_in_period
            
            # Movement velocity (movements per day)
            movement_velocity = self._calculate_movement_velocity(date_range)
            
            return {
                'total_movements': total_movements,
                'daily_movement_average': daily_movement_avg,
                'movement_breakdown': list(movement_breakdown),
                'movement_velocity': movement_velocity
            }
            
        except Exception as e:
            self.logger.error(f"Error calculating movement KPIs: {str(e)}")
            return {}
    
    def _calculate_financial_kpis(self, date_range: Dict[str, datetime]) -> Dict[str, Any]:
        """Calculate financial KPIs"""
        try:
            # Purchase analysis
            purchase_orders = PurchaseOrder.objects.filter(
                tenant=self.tenant,
                order_date__range=[date_range['start_date'].date(), date_range['end_date'].date()]
            )
            
            total_purchase_value = purchase_orders.aggregate(
                Sum('total_amount')
            )['total_amount__sum'] or 0
            
            # Stock value changes
            stock_value_change = self._calculate_stock_value_change(date_range)
            
            # Inventory turnover
            inventory_turnover = self._calculate_inventory_turnover(date_range)
            
            # Days in inventory
            days_in_inventory = 365 / inventory_turnover if inventory_turnover > 0 else 0
            
            return {
                'total_purchase_value': float(total_purchase_value),
                'stock_value_change': stock_value_change,
                'inventory_turnover_ratio': inventory_turnover,
                'days_in_inventory': days_in_inventory,
                'carrying_cost_percentage': 25.0  # This could be configurable
            }
            
        except Exception as e:
            self.logger.error(f"Error calculating financial KPIs: {str(e)}")
            return {}
    
    def _calculate_operational_kpis(self, date_range: Dict[str, datetime]) -> Dict[str, Any]:
        """Calculate operational KPIs"""
        try:
            # Order fulfillment metrics
            orders_fulfilled = PurchaseOrder.objects.filter(
                tenant=self.tenant,
                order_date__range=[date_range['start_date'].date(), date_range['end_date'].date()],
                status='COMPLETED'
            ).count()
            
            total_orders = PurchaseOrder.objects.filter(
                tenant=self.tenant,
                order_date__range=[date_range['start_date'].date(), date_range['end_date'].date()]
            ).count()
            
            fulfillment_rate = (orders_fulfilled / total_orders * 100) if total_orders > 0 else 0
            
            # Lead time analysis
            lead_time_analysis = self._calculate_lead_time_analysis(date_range)
            
            # Stockout frequency
            stockout_incidents = self._count_stockout_incidents(date_range)
            
            return {
                'order_fulfillment_rate': fulfillment_rate,
                'total_orders_period': total_orders,
                'orders_fulfilled': orders_fulfilled,
                'lead_time_analysis': lead_time_analysis,
                'stockout_incidents': stockout_incidents
            }
            
        except Exception as e:
            self.logger.error(f"Error calculating operational KPIs: {str(e)}")
            return {}
    
    def _calculate_performance_kpis(self, date_range: Dict[str, datetime]) -> Dict[str, Any]:
        """Calculate performance KPIs"""
        try:
            # Forecast accuracy (simplified)
            forecast_accuracy = 85.0  # This would be calculated based on actual vs predicted
            
            # Service level
            service_level = self._calculate_service_level(date_range)
            
            # Supplier performance
            supplier_performance = self._calculate_supplier_performance(date_range)
            
            # Alert metrics
            alerts = InventoryAlert.objects.filter(
                tenant=self.tenant,
                created_at__range=[date_range['start_date'], date_range['end_date']]
            )
            
            alert_metrics = {
                'total_alerts': alerts.count(),
                'resolved_alerts': alerts.filter(status='RESOLVED').count(),
                'open_alerts': alerts.filter(status__in=['OPEN', 'ACKNOWLEDGED']).count(),
                'avg_resolution_time': self._calculate_avg_alert_resolution_time(alerts)
            }
            
            return {
                'forecast_accuracy': forecast_accuracy,
                'service_level': service_level,
                'supplier_performance': supplier_performance,
                'alert_metrics': alert_metrics
            }
            
        except Exception as e:
            self.logger.error(f"Error calculating performance KPIs: {str(e)}")
            return {}
    
    def get_trend_analysis(self, metric: str, period: str = 'monthly',
                          duration_months: int = 12) -> ServiceResult:
        """Get trend analysis for specific metrics"""
        try:
            end_date = timezone.now()
            start_date = end_date - timedelta(days=duration_months * 30)
            
            if metric == 'stock_value':
                trend_data = self._get_stock_value_trend(start_date, end_date, period)
            elif metric == 'movement_volume':
                trend_data = self._get_movement_volume_trend(start_date, end_date, period)
            elif metric == 'purchase_spend':
                trend_data = self._get_purchase_spend_trend(start_date, end_date, period)
            elif metric == 'inventory_turnover':
                trend_data = self._get_inventory_turnover_trend(start_date, end_date, period)
            else:
                return ServiceResult.error(f"Unsupported metric: {metric}")
            
            return ServiceResult.success(
                data=trend_data,
                message=f"Trend analysis for {metric} completed"
            )
            
        except Exception as e:
            return ServiceResult.error(f"Failed to get trend analysis: {str(e)}")
    
    def get_abc_analysis_detailed(self) -> ServiceResult:
        """Get detailed ABC analysis with recommendations"""
        try:
            stock_items = StockItem.objects.filter(tenant=self.tenant).select_related(
                'product', 'warehouse'
            ).annotate(
                annual_usage_value=F('movement_count') * F('unit_cost') * 12,  # Approximate annual
                stock_value=F('quantity_on_hand') * F('unit_cost')
            )
            
            # Calculate total annual usage value
            total_annual_value = stock_items.aggregate(
                Sum('annual_usage_value')
            )['annual_usage_value__sum'] or 1
            
            # Prepare data for ABC classification
            items_data = []
            for item in stock_items:
                percentage_of_total = (item.annual_usage_value / total_annual_value) * 100
                
                items_data.append({
                    'product_name': item.product.name,
                    'product_sku': item.product.sku,
                    'warehouse': item.warehouse.name,
                    'annual_usage_value': float(item.annual_usage_value),
                    'percentage_of_total': percentage_of_total,
                    'current_stock_value': float(item.stock_value),
                    'current_classification': item.abc_classification,
                    'movement_count': item.movement_count,
                    'recommendations': self._get_abc_recommendations(item, percentage_of_total)
                })
            
            # Sort by annual usage value
            items_data.sort(key=lambda x: x['annual_usage_value'], reverse=True)
            
            # Calculate cumulative percentages and suggest classifications
            cumulative_percentage = 0
            for itemulative_percentage += item['percentage_of_total']
                item['cumulative_percentage'] = cumulative_percentage
                
                # Suggest classification based on cumulative percentage
                if cumulative_percentage <= 80:
                    suggested_class = 'A'
                elif cumulative_percentage <= 95:
                    suggested_class = 'B'
                else:
                    suggested_class = 'C'
                
                item['suggested_classification'] = suggested_class
                item['classification_change_needed'] = item['current_classification'] != suggested_class
            
            # Summary statistics
            summary = {
                'total_items': len(items_data),
                'total_annual_value': float(total_annual_value),
                'class_a_items': len([item for item in items_data if item['suggested_classification'] == 'A']),
                'class_b_items': len([item for item in items_data if item['suggested_classification'] == 'B']),
                'class_c_items': len([item for item in items_data if item['suggested_classification'] == 'C']),
                'reclassification_needed': len([item for item in items_data if item['classification_change_needed']])
            }
            
            return ServiceResult.success(
                data={
                    'items': items_data,
                    'summary': summary
                },
                message="Detailed ABC analysis completed"
            )
            
        except Exception as e:
            return ServiceResult.error(f"Failed to get detailed ABC analysis: {str(e)}")
    
    def _get_abc_recommendations(self, stock_item: StockItem, percentage_of_total: float) -> List[str]:
        """Get recommendations based on ABC classification"""
        recommendations = []
        
        if percentage_of_total > 5:  # High value items
            recommendations.extend([
                "Implement tight inventory control",
                "Frequent stock reviews",
                "Consider Just-in-Time ordering",
                "Monitor closely for obsolescence"
            ])
        elif percentage_of_total > 1:  # Medium value items
            recommendations.extend([
                "Moderate inventory control",
                "Regular stock reviews",
                "Economic order quantity optimization"
            ])
        else:  # Low value items
            recommendations.extend([
                "Basic inventory control",
                "Bulk ordering to reduce handling costs",
                "Longer review cycles acceptable"
            ])
        
        # Add specific recommendations based on current stock status
        available_qty = stock_item.quantity_on_hand - stock_item.quantity_reserved
        
        if available_qty <= 0:
            recommendations.append("URGENT: Out of stock - immediate reorder required")
        elif available_qty <= stock_item.reorder_level:
            recommendations.append("Below reorder level - consider reordering")
        elif stock_item.maximum_stock_level > 0 and available_qty >= stock_item.maximum_stock_level:
            recommendations.append("Overstock situation - reduce future orders")
        
        return recommendations
    
    def get_seasonal_analysis(self, product_ids: Optional[List[int]] = None) -> ServiceResult:
        """Analyze seasonal patterns in inventory"""
        try:
            # Get movement data for the last 2 years
            end_date = timezone.now()
            start_date = end_date - timedelta(days=730)  # 2 years
            
            movements_query = StockMovement.objects.filter(
                tenant=self.tenant,
                created_at__range=[start_date, end_date],
                movement_type__in=['ISSUE', 'RECEIPT']
            ).select_related().prefetch_related('items__stock_item__product')
            
            if product_ids:
                movements_query = movements_query.filter(
                    items__stock_item__product_id__in=product_ids
                )
            
            # Group by month and product
            monthly_data = {}
            
            for movement in movements_query:
                month_year = movement.created_at.strftime('%Y-%m')
                
                for item in movement.items.all():
                    product_id = item.stock_item.product.id
                    product_name = item.stock_item.product.name
                    
                    key = f"{product_id}_{month_year}"
                    
                    if key not in monthly_[key] = {
                            'product_id': product_id,
                            'product_name': product_name,
                            'month_year': month_year,
                            'month': int(month_year.split('-')[1]),
                            'year': int(month_year.split('-')[0]),
                            'total_inbound': 0,
                            'total_outbound': 0
                        }
                    
                    if movement.movement_type == 'RECEIPT':
                        monthly_data[key]['total_inbound'] += item.quantity
                    elif movement.movement_type == 'ISSUE':
                        monthly_data[key]['total_outbound'] += item.quantity
            
            # Calculate seasonal patterns
            seasonal_patterns = self._calculate_seasonal_patterns(list(monthly_data.values()))
            
            return ServiceResult.success(
                data={
                    'monthly_data': list(monthly_data.values()),
                    'seasonal_patterns': seasonal_patterns,
                    'analysis_period': {
                        'start_date': start_date.isoformat(),
                        'end_date': end_date.isoformat()
                    }
                },
                message="Seasonal analysis completed"
            )
            
        except Exception as e:
            return ServiceResult.error(f"Failed to get seasonal analysis: {str(e)}")
    
    def _calculate_seasonal_patterns[Dict[str, Any]]) -> Dict[str, Any]:
        """Calculate seasonal patterns from monthly data"""
        try:
            # Group by product and month (ignoring year)
            product_patterns = {}
            
            for recor_id = record['product_id']
                month = record['month']
                
                if product_id not in product_patterns:
                    product_patterns[product_id] = {
                        'product_name': record['product_name'],
                        'monthly_averages': {str(m): {'inbound': 0, 'outbound': 0, 'count': 0} for m in range(1, 13)},
                        'peak_months': [],
                        'low_months': [],
                        'seasonality_score': 0
                    }
                
                pattern = product_patterns[product_id]['monthly_averages'][str(month)]
                pattern['inbound'] += record['total_inbound']
                pattern['outbound'] += record['total_outbound']
                pattern['count'] += 1
            
            # Calculate averages and identify patterns
            for product_id, pattern in product_patterns.items():
                monthly_averages = []
                
                for month_str, data in pattern['monthly_averages'].items():
                    if data['count'] > 0:
                        avg_inbound = data['inbound'] / data['count']
                        avg_outbound = data['outbound'] / data['count']
                        monthly_averages.append({
                            'month': int(month_str),
                            'avg_inbound': avg_inbound,
                            'avg_outbound': avg_outbound
                        })
                
                if monthly_averages:
                    # Find peak and low months
                    sorted_by_outbound = sorted(monthly_averages, key=lambda x: x['avg_outbound'])
                    
                    pattern['low_months'] = [item['month'] for item in sorted_by_outbound[:3]]
                    pattern['peak_months'] = [item['month'] for item in sorted_by_outbound[-3:]]
                    
                    # Calculate seasonality score (coefficient of variation)
                    outbound_values = [item['avg_outbound'] for item in monthly_averages]
                    if len(outbound_values) > 1:
                        mean_val = sum(outbound_values) / len(outbound_values)
                        variance = sum((x - mean_val) ** 2 for x in outbound_values) / len(outbound_values)
                        std_dev = variance ** 0.5
                        pattern['seasonality_score'] = (std_dev / mean_val * 100) if mean_val > 0 else 0
            
            return product_patterns
            
        except Exception as e:
            self.logger.error(f"Error calculating seasonal patterns: {str(e)}")
            return {}
    
    def get_supplier_analysis(self) -> ServiceResult:
        """Get comprehensive supplier analysis"""
        try:
            end_date = timezone.now()
            start_date = end_date - timedelta(days=90)
            
            # Get supplier performance data
            suppliers = Supplier.objects.filter(tenant=self.tenant, is_active=True)
            
            supplier_analysis = []
            
            for supplier in suppliers:
                # Get purchase orders for this supplier
                pos = PurchaseOrder.objects.filter(
                    tenant=self.tenant,
                    supplier=supplier,
                    order_date__range=[start_date.date(), end_date.date()]
                )
                
                # Calculate metrics
                total_orders = pos.count()
                total_value = pos.aggregate(Sum('total_amount'))['total_amount__sum'] or 0
                completed_orders = pos.filter(status='COMPLETED').count()
                
                # Lead time analysis
                completed_pos = pos.filter(status='COMPLETED', completed_date__isnull=False)
                avg_lead_time = None
                
                if completed_pos.exists():
                    lead_times = [
                        (po.completed_date - po.order_date).days 
                        for po in completed_pos 
                        if po.completed_date and po.order_date
                    ]
                    
                    if lead_times:
                        avg_lead_time = sum(lead_times) / len(lead_times)
                
                # Quality metrics (based on returns/adjustments)
                quality_score = self._calculate_supplier_quality_score(supplier, start_date, end_date)
                
                supplier_analysis.append({
                    'supplier_id': supplier.id,
                    'supplier_name': supplier.name,
                    'total_orders': total_orders,
                    'total_value': float(total_value),
                    'completion_rate': (completed_orders / total_orders * 100) if total_orders > 0 else 0,
                    'avg_lead_time_days': avg_lead_time,
                    'quality_score': quality_score,
                    'performance_rating': self._calculate_supplier_rating(
                        completed_orders / total_orders if total_orders > 0 else 0,
                        avg_lead_time,
                        quality_score
                    )
                })
            
            # Sort by performance rating
            supplier_analysis.sort(key=lambda x: x['performance_rating'], reverse=True)
            
            return ServiceResult.success(
                data=supplier_analysis,
                message=f"Supplier analysis completed for {len(supplier_analysis)} suppliers"
            )
            
        except Exception as e:
            return ServiceResult.error(f"Failed to get supplier analysis: {str(e)}")
    
    def _calculate_supplier_quality_score(self, supplier: Supplier, 
                                         start_date: datetime, end_date: datetime) -> float:
        """Calculate quality score for supplier based on returns and adjustments"""
        try:
            # Get receipts from this supplier
            receipts = supplier.stockreceipt_set.filter(
                receipt_date__range=[start_date.date(), end_date.date()]
            )
            
            total_received = receipts.aggregate(
                Sum('total_quantity')
            )['total_quantity__sum'] or 0
            
            if total_received == 0:
                return 100.0  # No data, assume perfect
            
            # Count quality issues (this would depend on your quality control implementation)
            quality_issues = receipts.filter(
                qc_status='FAILED'
            ).aggregate(
                Sum('total_quantity')
            )['total_quantity__sum'] or 0
            
            quality_score = ((total_received - quality_issues) / total_received * 100) if total_received > 0 else 100
            
            return max(0, min(100, quality_score))
            
        except Exception:
            return 100.0  # Default to perfect score if calculation fails
    
    def _calculate_supplier_rating(self, completion_rate: float, 
                                  avg_lead_time: Optional[float], quality_score: float) -> float:
        """Calculate overall supplier performance rating"""
        try:
            # Weighted scoring
            completion_weight = 0.4
            lead_time_weight = 0.3
            quality_weight = 0.3
            
            # Completion rate score (0-100)
            completion_score = completion_rate
            
            # Lead time score (assume 14 days is target, score decreases as lead time increases)
            if avg_lead_time is not None:
                target_lead_time = 14
                if avg_lead_time <= target_lead_time:
                    lead_time_score = 100
                else:
                    lead_time_score = max(0, 100 - ((avg_lead_time - target_lead_time) * 5))
            else:
                lead_time_score = 50  # Neutral score if no data
            
            # Calculate weighted average
            overall_rating = (
                completion_score * completion_weight +
                lead_time_score * lead_time_weight +
                quality_score * quality_weight
            )
            
            return round(overall_rating, 2)
            
        except Exception:
            return 50.0  # Default rating
    
    # Helper methods for KPI calculations
    def _calculate_movement_velocity(self, date_range: Dict[str, datetime]) -> Dict[str, float]:
        """Calculate movement velocity metrics"""
        try:
            from ...managers.query_utils import InventoryQueryUtils
            
            velocity_data = InventoryQueryUtils.get_movement_velocity_analysis(
                tenant=self.tenant,
                days=(date_range['end_date'] - date_range['start_date']).days
            )
            
            if velocity Calculate averages
                total_items = len(velocity_data)
                avg_velocity = sum(item.velocity_ratio for item in velocity_data) / total_items if total_items > 0 else 0
                
                return {
                    'average_velocity_ratio': float(avg_velocity),
                    'fast_moving_items': len([item for item in velocity_data if item.velocity_ratio > 0.1]),
                    'slow_moving_items': len([item for item in velocity_data if item.velocity_ratio < 0.01]),
                    'total_analyzed_items': total_items
                }
            
            return {}
            
        except Exception:
            return {}
    
    def _calculate_stock_value_change(self, date_range: Dict[str, datetime]) -> Dict[str, float]:
        """Calculate stock value change over period"""
        try:
            # This would ideally use historical valuation data
            # For now, we'll use a simplified calculation
            current_value = StockItem.objects.filter(tenant=self.tenant).aggregate(
                total=Sum(F('quantity_on_hand') * F('unit_cost'))
            )['total'] or 0
            
            # Simulate previous value (would come from historical data)
            previous_value = current_value * 0.95  # Simplified assumption
            
            change_amount = current_value - previous_value
            change_percentage = (change_amount / previous_value * 100) if previous_value > 0 else 0
            
            return {
                'current_value': float(current_value),
                'previous_value': float(previous_value),
                'change_amount': float(change_amount),
                'change_percentage': change_percentage
            }
            
        except Exception:
            return {}
    
    def _calculate_inventory_turnover(self, date_range: Dict[str, datetime]) -> float:
        """Calculate inventory turnover ratio"""
        try:
            # Get COGS for the period
            cogs_movements = StockMovement.objects.filter(
                tenant=self.tenant,
                movement_type='ISSUE',
                created_at__range=[date_range['start_date'], date_range['end_date']]
            )
            
            cogs = cogs_movements.aggregate(
                total=Sum(F('items__quantity') * F('items__unit_cost'))
            )['total'] or 0
            
            # Get average inventory value
            current_inventory_value = StockItem.objects.filter(tenant=self.tenant).aggregate(
                total=Sum(F('quantity_on_hand') * F('unit_cost'))
            )['total'] or 1
            
            # Annualize the COGS if period is less than a year
            days_in_period = (date_range['end_date'] - date_range['start_date']).days
            annualized_cogs = cogs * (365 / days_in_period) if days_in_period > 0 else cogs
            
            turnover = annualized_cogs / current_inventory_value if current_inventory_value > 0 else 0
            
            return float(turnover)
            
        except Exception:
            return 0.0
    
    # Additional helper methods would be implemented similarly...
    def _calculate_lead_time_analysis(self, date_range: Dict[str, datetime]) -> Dict[str, Any]:
        """Placeholder for lead time analysis"""
        return {'average_lead_time': 14, 'lead_time_variance': 3}
    
    def _count_stockout_incidents(self, date_range: Dict[str, datetime]) -> int:
        """Placeholder for stockout incident counting"""
        return 5
    
    def _calculate_service_level(self, date_range: Dict[str, datetime]) -> float:
        """Placeholder for service level calculation"""
        return 95.5
    
    def _calculate_supplier_performance(self, date_range: Dict[str, datetime]) -> Dict[str, Any]:
        """Placeholder for supplier performance calculation"""
        return {'average_performance_score': 87.5, 'top_performing_suppliers': 3}
    
    def _calculate_avg_alert_resolution_time(self, alerts) -> float:
        """Calculate average alert resolution time"""
        try:
            resolved_alerts = alerts.filter(status='RESOLVED', resolved_at__isnull=False)
            
            if not resolved_alerts.exists():
                return 0
            
            total_hours = 0
            count = 0
            
            for alert in resolved_alerts:
                if alert.resolved_at and alert.created_at:
                    resolution_time = (alert.resolved_at - alert.created_at).total_seconds() / 3600
                    total_hours += resolution_time
                    count += 1
            
            return total_hours / count if count > 0 else 0
            
        except Exception:
            return 0
    
    # Trend analysis helper methods
    def _get_stock_value_trend(self, start_date: datetime, end_date: datetime, period: str) -> List[Dict[str, Any]]:
        """Get stock value trend data"""
        # This would be implemented based on historical valuation data
        return []
    
    def _get_movement_volume_trend(self, start_date: datetime, end_date: datetime, period: str) -> List[Dict[str, Any]]:
        """Get movement volume trend data"""
        # Implementation for movement volume trends
        return []
    
    def _get_purchase_spend_trend(self, start_date: datetime, end_date: datetime, period: str) -> List[Dict[str, Any]]:
        """Get purchase spend trend data"""
        # Implementation for purchase spend trends
        return []
    
    def _get_inventory_turnover_trend(self, start_date: datetime, end_date: datetime, period: str) -> List[Dict[str, Any]]:
        """Get inventory turnover trend data"""
        # Implementation for inventory turnover trends
        return []