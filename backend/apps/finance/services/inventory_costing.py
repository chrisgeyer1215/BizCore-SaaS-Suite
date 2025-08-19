"""
Finance Services - Inventory Costing Service
Advanced inventory cost layer management with landed costs and adjustments
"""

from django.db import transaction, models
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.db.models import Sum, F, Q, Case, When, DecimalField, Max, Min
from decimal import Decimal, ROUND_HALF_UP
from datetime import date, datetime, timedelta
import logging
from typing import Dict, List, Optional, Tuple, Any

from apps.core.utils import generate_code
from ..models import (
    InventoryCostLayer, InventoryCostConsumption, LandedCost, LandedCostAllocation,
    Account, JournalEntry, JournalEntryLine, Product, Warehouse, FinanceSettings,
    Currency, StockMovement, PurchaseOrder, Bill, BillItem, Invoice, InvoiceItem
)


logger = logging.getLogger(__name__)


class InventoryCostingService:
    """Advanced inventory costing service for cost layer management and landed costs"""
    
    def __init__(self, tenant):
        self.tenant = tenant
        self.settings = self._get_finance_settings()
        self.base_currency = self._get_base_currency()
        self.valuation_method = self.settings.inventory_valuation_method
    
    def _get_finance_settings(self):
        """Get finance settings for tenant"""
        try:
            return FinanceSettings.objects.get(tenant=self.tenant)
        except FinanceSettings.DoesNotExist:
            return FinanceSettings.objects.create(
                tenant=self.tenant,
                company_name=f"{self.tenant.name} Inc.",
                inventory_valuation_method='FIFO'
            )
    
    def _get_base_currency(self):
        """Get base currency for tenant"""
        try:
            return Currency.objects.get(
                tenant=self.tenant,
                code=self.settings.base_currency,
                is_active=True
            )
        except Currency.DoesNotExist:
            return Currency.objects.create(
                tenant=self.tenant,
                code=self.settings.base_currency,
                name='US Dollar',
                symbol='$',
                is_base_currency=True
            )
    
    # ============================================================================
    # COST LAYER CREATION & MANAGEMENT
    # ============================================================================
    
    @transaction.atomic
    def create_purchase_cost_layer(self, purchase_data: Dict) -> InventoryCostLayer:
        """
        Create inventory cost layer for purchased goods
        
        Args:
            purchase_data: Dictionary with purchase details
                - product_id: Product ID
                - warehouse_id: Warehouse ID
                - quantity: Quantity purchased
                - unit_cost: Unit cost in purchase currency
                - currency_code: Purchase currency
                - exchange_rate: Exchange rate to base currency
                - purchase_date: Date of purchase
                - source_document_type: Source document type
                - source_document_id: Source document ID
                - source_document_number: Source document number
                - vendor_id: Vendor ID (optional)
                - purchase_order_id: Purchase order ID (optional)
        
        Returns:
            Created InventoryCostLayer instance
        """
        try:
            # Validate required fields
            required_fields = ['product_id', 'warehouse_id', 'quantity', 'unit_cost', 'purchase_date']
            for field in required_fields:
                if field not in purchase_data or purchase_data[field] is None:
                    raise ValidationError(f"Missing required field: {field}")
            
            # Get currency and exchange rate
            currency_code = purchase_data.get('currency_code', self.base_currency.code)
            currency = Currency.objects.get(tenant=self.tenant, code=currency_code)
            exchange_rate = purchase_data.get('exchange_rate', Decimal('1.000000'))
            
            # Calculate costs
            quantity = Decimal(str(purchase_data['quantity']))
            unit_cost = Decimal(str(purchase_data['unit_cost']))
            total_cost = quantity * unit_cost
            
            base_currency_unit_cost = unit_cost * exchange_rate
            base_currency_total_cost = total_cost * exchange_rate
            
            # Create cost layer
            cost_layer = InventoryCostLayer.objects.create(
                tenant=self.tenant,
                product_id=purchase_data['product_id'],
                warehouse_id=purchase_data['warehouse_id'],
                layer_type='PURCHASE',
                quantity=quantity,
                unit_cost=unit_cost,
                total_cost=total_cost,
                currency=currency,
                exchange_rate=exchange_rate,
                base_currency_unit_cost=base_currency_unit_cost,
                base_currency_total_cost=base_currency_total_cost,
                source_document_type=purchase_data.get('source_document_type', 'MANUAL'),
                source_document_id=purchase_data.get('source_document_id'),
                source_document_number=purchase_data.get('source_document_number', ''),
                acquisition_date=purchase_data['purchase_date'],
                quantity_remaining=quantity
            )
            
            logger.info(f"Purchase cost layer created: {cost_layer.id} for product {purchase_data['product_id']}")
            return cost_layer
            
        except Exception as e:
            logger.error(f"Error creating purchase cost layer: {str(e)}")
            raise ValidationError(f"Failed to create cost layer: {str(e)}")
    
    @transaction.atomic
    def create_adjustment_cost_layer(self, adjustment_data: Dict, user) -> InventoryCostLayer:
        """
        Create cost layer for inventory adjustments
        
        Args:
            adjustment_data: Dictionary with adjustment details
            user: User creating the adjustment
        
        Returns:
            Created InventoryCostLayer instance
        """
        try:
            # Validate adjustment data
            required_fields = ['product_id', 'warehouse_id', 'quantity_adjustment', 'reason']
            for field in required_fields:
                if field not in adjustment_data:
                    raise ValidationError(f"Missing required field: {field}")
            
            quantity_adjustment = Decimal(str(adjustment_data['quantity_adjustment']))
            
            if quantity_adjustment == 0:
                raise ValidationError("Quantity adjustment cannot be zero")
            
            # Get current weighted average cost for the product
            current_cost = self.get_weighted_average_cost(
                adjustment_data['product_id'],
                adjustment_data['warehouse_id']
            )
            
            # Use provided unit cost or current weighted average
            unit_cost = Decimal(str(adjustment_data.get('unit_cost', current_cost)))
            
            if quantity_adjustment > 0:
                # Positive adjustment (increase inventory)
                layer_type = 'ADJUSTMENT'
                quantity = quantity_adjustment
            else:
                # Negative adjustment (decrease inventory) - handle differently
                return self._process_negative_adjustment(adjustment_data, user)
            
            total_cost = quantity * unit_cost
            
            # Create cost layer
            cost_layer = InventoryCostLayer.objects.create(
                tenant=self.tenant,
                product_id=adjustment_data['product_id'],
                warehouse_id=adjustment_data['warehouse_id'],
                layer_type=layer_type,
                quantity=quantity,
                unit_cost=unit_cost,
                total_cost=total_cost,
                currency=self.base_currency,
                exchange_rate=Decimal('1.000000'),
                base_currency_unit_cost=unit_cost,
                base_currency_total_cost=total_cost,
                source_document_type='ADJUSTMENT',
                source_document_number=f"ADJ-{timezone.now().strftime('%Y%m%d-%H%M%S')}",
                acquisition_date=adjustment_data.get('adjustment_date', date.today()),
                quantity_remaining=quantity
            )
            
            logger.info(f"Adjustment cost layer created: {cost_layer.id}")
            return cost_layer
            
        except Exception as e:
            logger.error(f"Error creating adjustment cost layer: {str(e)}")
            raise ValidationError(f"Failed to create adjustment cost layer: {str(e)}")
    
    def _process_negative_adjustment(self, adjustment_data: Dict, user) -> InventoryCostLayer:
        """Process negative inventory adjustment by consuming existing layers"""
        
        quantity_to_remove = abs(Decimal(str(adjustment_data['quantity_adjustment'])))
        
        # Get available cost layers (using FIFO for adjustments)
        available_layers = InventoryCostLayer.objects.filter(
            tenant=self.tenant,
            product_id=adjustment_data['product_id'],
            warehouse_id=adjustment_data['warehouse_id'],
            quantity_remaining__gt=0,
            is_fully_consumed=False
        ).order_by('acquisition_date', 'created_date')
        
        total_available = available_layers.aggregate(
            total=Sum('quantity_remaining')
        )['total'] or Decimal('0.00')
        
        if quantity_to_remove > total_available:
            raise ValidationError(
                f"Cannot remove {quantity_to_remove} units. Only {total_available} available."
            )
        
        # Consume layers
        remaining_to_remove = quantity_to_remove
        total_cost_removed = Decimal('0.00')
        
        for layer in available_layers:
            if remaining_to_remove <= 0:
                break
            
            quantity_consumed = min(layer.quantity_remaining, remaining_to_remove)
            cost_consumed = quantity_consumed * layer.effective_unit_cost
            
            # Create consumption record
            InventoryCostConsumption.objects.create(
                tenant=self.tenant,
                cost_layer=layer,
                quantity_consumed=quantity_consumed,
                unit_cost=layer.effective_unit_cost,
                total_cost=cost_consumed,
                consumption_date=adjustment_data.get('adjustment_date', date.today()),
                source_document_type='ADJUSTMENT'
            )
            
            # Update layer
            layer.quantity_remaining -= quantity_consumed
            if layer.quantity_remaining <= Decimal('0.0001'):
                layer.quantity_remaining = Decimal('0.00')
                layer.is_fully_consumed = True
            layer.save()
            
            total_cost_removed += cost_consumed
            remaining_to_remove -= quantity_consumed
        
        # Create negative cost layer for tracking
        avg_cost = total_cost_removed / quantity_to_remove if quantity_to_remove > 0 else Decimal('0.00')
        
        negative_layer = InventoryCostLayer.objects.create(
            tenant=self.tenant,
            product_id=adjustment_data['product_id'],
            warehouse_id=adjustment_data['warehouse_id'],
            layer_type='ADJUSTMENT',
            quantity=-quantity_to_remove,
            unit_cost=avg_cost,
            total_cost=-total_cost_removed,
            currency=self.base_currency,
            exchange_rate=Decimal('1.000000'),
            base_currency_unit_cost=avg_cost,
            base_currency_total_cost=-total_cost_removed,
            source_document_type='ADJUSTMENT',
            source_document_number=f"ADJ-{timezone.now().strftime('%Y%m%d-%H%M%S')}",
            acquisition_date=adjustment_data.get('adjustment_date', date.today()),
            quantity_remaining=Decimal('0.00'),
            is_fully_consumed=True
        )
        
        return negative_layer
    
    @transaction.atomic
    def create_transfer_cost_layers(self, transfer_data: Dict) -> Tuple[InventoryCostLayer, InventoryCostLayer]:
        """
        Create cost layers for inventory transfers between warehouses
        
        Args:
            transfer_data: Dictionary with transfer details
        
        Returns:
            Tuple of (outbound_layer, inbound_layer)
        """
        try:
            # Validate transfer data
            required_fields = ['product_id', 'from_warehouse_id', 'to_warehouse_id', 'quantity', 'transfer_date']
            for field in required_fields:
                if field not in transfer_data:
                    raise ValidationError(f"Missing required field: {field}")
            
            quantity = Decimal(str(transfer_data['quantity']))
            
            # Calculate cost using existing inventory
            cost_data = self._calculate_transfer_cost(
                transfer_data['product_id'],
                transfer_data['from_warehouse_id'],
                quantity
            )
            
            if not cost_data['sufficient_inventory']:
                raise ValidationError(f"Insufficient inventory for transfer: {cost_data['shortage']}")
            
            # Create outbound (negative) layer
            outbound_layer = InventoryCostLayer.objects.create(
                tenant=self.tenant,
                product_id=transfer_data['product_id'],
                warehouse_id=transfer_data['from_warehouse_id'],
                layer_type='TRANSFER_OUT',
                quantity=-quantity,
                unit_cost=cost_data['average_unit_cost'],
                total_cost=-cost_data['total_cost'],
                currency=self.base_currency,
                exchange_rate=Decimal('1.000000'),
                base_currency_unit_cost=cost_data['average_unit_cost'],
                base_currency_total_cost=-cost_data['total_cost'],
                source_document_type='TRANSFER',
                source_document_number=transfer_data.get('transfer_number', ''),
                acquisition_date=transfer_data['transfer_date'],
                quantity_remaining=Decimal('0.00'),
                is_fully_consumed=True
            )
            
            # Create inbound (positive) layer
            inbound_layer = InventoryCostLayer.objects.create(
                tenant=self.tenant,
                product_id=transfer_data['product_id'],
                warehouse_id=transfer_data['to_warehouse_id'],
                layer_type='TRANSFER_IN',
                quantity=quantity,
                unit_cost=cost_data['average_unit_cost'],
                total_cost=cost_data['total_cost'],
                currency=self.base_currency,
                exchange_rate=Decimal('1.000000'),
                base_currency_unit_cost=cost_data['average_unit_cost'],
                base_currency_total_cost=cost_data['total_cost'],
                source_document_type='TRANSFER',
                source_document_number=transfer_data.get('transfer_number', ''),
                acquisition_date=transfer_data['transfer_date'],
                quantity_remaining=quantity
            )
            
            # Consume source inventory
            self._consume_transfer_inventory(
                transfer_data['product_id'],
                transfer_data['from_warehouse_id'],
                quantity,
                cost_data['layers_to_consume']
            )
            
            logger.info(f"Transfer cost layers created: OUT-{outbound_layer.id}, IN-{inbound_layer.id}")
            return outbound_layer, inbound_layer
            
        except Exception as e:
            logger.error(f"Error creating transfer cost layers: {str(e)}")
            raise ValidationError(f"Failed to create transfer cost layers: {str(e)}")
    
    def _calculate_transfer_cost(self, product_id: int, from_warehouse_id: int, 
                               quantity: Decimal) -> Dict:
        """Calculate cost for inventory transfer"""
        
        # Get available layers using current valuation method
        if self.valuation_method == 'FIFO':
            available_layers = InventoryCostLayer.objects.filter(
                tenant=self.tenant,
                product_id=product_id,
                warehouse_id=from_warehouse_id,
                quantity_remaining__gt=0,
                is_fully_consumed=False
            ).order_by('acquisition_date', 'created_date')
        elif self.valuation_method == 'LIFO':
            available_layers = InventoryCostLayer.objects.filter(
                tenant=self.tenant,
                product_id=product_id,
                warehouse_id=from_warehouse_id,
                quantity_remaining__gt=0,
                is_fully_consumed=False
            ).order_by('-acquisition_date', '-created_date')
        else:  # Weighted Average
            available_layers = InventoryCostLayer.objects.filter(
                tenant=self.tenant,
                product_id=product_id,
                warehouse_id=from_warehouse_id,
                quantity_remaining__gt=0,
                is_fully_consumed=False
            )
        
        total_available = available_layers.aggregate(
            total=Sum('quantity_remaining')
        )['total'] or Decimal('0.00')
        
        sufficient_inventory = total_available >= quantity
        shortage = max(Decimal('0.00'), quantity - total_available)
        
        if not sufficient_inventory:
            return {
                'sufficient_inventory': False,
                'shortage': shortage,
                'total_cost': Decimal('0.00'),
                'average_unit_cost': Decimal('0.00'),
                'layers_to_consume': []
            }
        
        # Calculate cost based on method
        if self.valuation_method == 'WEIGHTED_AVERAGE':
            # Calculate weighted average cost
            totals = available_layers.aggregate(
                total_quantity=Sum('quantity_remaining'),
                total_cost=Sum(F('quantity_remaining') * F('base_currency_unit_cost'))
            )
            
            avg_cost = (totals['total_cost'] / totals['total_quantity']) if totals['total_quantity'] > 0 else Decimal('0.00')
            total_cost = quantity * avg_cost
            
            # For weighted average, consume proportionally
            layers_to_consume = []
            remaining_quantity = quantity
            
            for layer in available_layers:
                if remaining_quantity <= 0:
                    break
                
                proportion = layer.quantity_remaining / totals['total_quantity']
                consume_qty = min(quantity * proportion, layer.quantity_remaining, remaining_quantity)
                
                if consume_qty > 0:
                    layers_to_consume.append({
                        'layer': layer,
                        'quantity': consume_qty,
                        'cost': consume_qty * avg_cost
                    })
                    remaining_quantity -= consume_qty
        
        else:  # FIFO or LIFO
            layers_to_consume = []
            remaining_quantity = quantity
            total_cost = Decimal('0.00')
            
            for layer in available_layers:
                if remaining_quantity <= 0:
                    break
                
                consume_qty = min(layer.quantity_remaining, remaining_quantity)
                layer_cost = consume_qty * layer.effective_unit_cost
                
                layers_to_consume.append({
                    'layer': layer,
                    'quantity': consume_qty,
                    'cost': layer_cost
                })
                
                total_cost += layer_cost
                remaining_quantity -= consume_qty
            
            avg_cost = total_cost / quantity if quantity > 0 else Decimal('0.00')
        
        return {
            'sufficient_inventory': True,
            'shortage': Decimal('0.00'),
            'total_cost': total_cost,
            'average_unit_cost': avg_cost,
            'layers_to_consume': layers_to_consume
        }
    
    def _consume_transfer_inventory(self, product_id: int, warehouse_id: int, 
                                  quantity: Decimal, layers_to_consume: List[Dict]):
        """Consume inventory for transfer"""
        
        for layer_data in layers_to_consume:
            layer = layer_data['layer']
            consume_qty = layer_data['quantity']
            
            # Create consumption record
            InventoryCostConsumption.objects.create(
                tenant=self.tenant,
                cost_layer=layer,
                quantity_consumed=consume_qty,
                unit_cost=layer.effective_unit_cost,
                total_cost=layer_data['cost'],
                consumption_date=date.today(),
                source_document_type='TRANSFER'
            )
            
            # Update layer
            layer.quantity_remaining -= consume_qty
            if layer.quantity_remaining <= Decimal('0.0001'):
                layer.quantity_remaining = Decimal('0.00')
                layer.is_fully_consumed = True
            layer.save()
    
    # ============================================================================
    # LANDED COST MANAGEMENT
    # ============================================================================
    
    @transaction.atomic
    def allocate_landed_costs(self, landed_cost_data: Dict) -> LandedCost:
        """
        Allocate landed costs to inventory cost layers
        
        Args:
            landed_cost_data: Dictionary with landed cost details
                - purchase_order_id: Related purchase order ID
                - total_amount: Total landed cost amount
                - cost_type: Type of landed cost (FREIGHT, DUTY, etc.)
                - allocation_method: How to allocate (QUANTITY, VALUE, WEIGHT)
                - description: Description of the cost
                - vendor_id: Vendor ID for the landed cost
        
        Returns:
            Created LandedCost instance
        """
        try:
            # Create landed cost record
            landed_cost = LandedCost.objects.create(
                tenant=self.tenant,
                reference_number=self._generate_landed_cost_number(),
                description=landed_cost_data['description'],
                total_landed_cost=Decimal(str(landed_cost_data['total_amount'])),
                allocation_method=landed_cost_data.get('allocation_method', 'VALUE'),
                source_document_type='PURCHASE_ORDER',
                source_document_id=landed_cost_data.get('purchase_order_id'),
                source_purchase_order_id=landed_cost_data.get('purchase_order_id')
            )
            
            # Get related cost layers to allocate to
            if landed_cost_data.get('purchase_order_id'):
                cost_layers = InventoryCostLayer.objects.filter(
                    tenant=self.tenant,
                    source_document_type='BILL',
                    source_document_id__in=Bill.objects.filter(
                        source_purchase_order_id=landed_cost_data['purchase_order_id']
                    ).values_list('id', flat=True)
                )
            else:
                # Manual allocation - get specific cost layers
                cost_layer_ids = landed_cost_data.get('cost_layer_ids', [])
                cost_layers = InventoryCostLayer.objects.filter(
                    tenant=self.tenant,
                    id__in=cost_layer_ids
                )
            
            if not cost_layers.exists():
                raise ValidationError("No cost layers found for landed cost allocation")
            
            # Allocate based on method
            allocations = self._calculate_landed_cost_allocations(
                landed_cost, 
                cost_layers, 
                landed_cost_data.get('allocation_method', 'VALUE')
            )
            
            # Apply allocations
            for allocation in allocations:
                # Create allocation record
                LandedCostAllocation.objects.create(
                    tenant=self.tenant,
                    landed_cost=landed_cost,
                    cost_layer=allocation['cost_layer'],
                    allocated_amount=allocation['amount'],
                    allocation_percentage=allocation['percentage']
                )
                
                # Update cost layer
                cost_layer = allocation['cost_layer']
                cost_layer.allocated_landed_costs += allocation['amount']
                cost_layer.save()
            
            # Mark as allocated
            landed_cost.is_allocated = True
            landed_cost.allocated_date = timezone.now()
            landed_cost.save()
            
            logger.info(f"Landed costs allocated: {landed_cost.reference_number}")
            return landed_cost
            
        except Exception as e:
            logger.error(f"Error allocating landed costs: {str(e)}")
            raise ValidationError(f"Failed to allocate landed costs: {str(e)}")
    
    def _calculate_landed_cost_allocations(self, landed_cost: LandedCost, 
                                         cost_layers, allocation_method: str) -> List[Dict]:
        """Calculate how to allocate landed costs across cost layers"""
        
        allocations = []
        total_to_allocate = landed_cost.total_landed_cost
        
        if allocation_method == 'QUANTITY':
            # Allocate based on quantity
            total_quantity = cost_layers.aggregate(
                total=Sum('quantity')
            )['total'] or Decimal('0.00')
            
            if total_quantity == 0:
                return allocations
            
            for layer in cost_layers:
                percentage = (layer.quantity / total_quantity) * 100
                amount = (layer.quantity / total_quantity) * total_to_allocate
                
                allocations.append({
                    'cost_layer': layer,
                    'amount': amount,
                    'percentage': percentage
                })
        
        elif allocation_method == 'VALUE':
            # Allocate based on value
            total_value = cost_layers.aggregate(
                total=Sum('base_currency_total_cost')
            )['total'] or Decimal('0.00')
            
            if total_value == 0:
                return allocations
            
            for layer in cost_layers:
                percentage = (layer.base_currency_total_cost / total_value) * 100
                amount = (layer.base_currency_total_cost / total_value) * total_to_allocate
                
                allocations.append({
                    'cost_layer': layer,
                    'amount': amount,
                    'percentage': percentage
                })
        
        elif allocation_method == 'WEIGHT':
            # Allocate based on weight (requires weight data)
            # For now, fall back to quantity allocation
            return self._calculate_landed_cost_allocations(landed_cost, cost_layers, 'QUANTITY')
        
        else:  # MANUAL
            # Equal allocation across all layers
            layer_count = cost_layers.count()
            if layer_count == 0:
                return allocations
            
            amount_per_layer = total_to_allocate / layer_count
            percentage_per_layer = Decimal('100.00') / layer_count
            
            for layer in cost_layers:
                allocations.append({
                    'cost_layer': layer,
                    'amount': amount_per_layer,
                    'percentage': percentage_per_layer
                })
        
        return allocations
    
    def _generate_landed_cost_number(self) -> str:
        """Generate unique landed cost reference number"""
        return generate_code('LC', self.tenant.id)
    
    # ============================================================================
    # COST ANALYSIS & REPORTING
    # ============================================================================
    
    def get_weighted_average_cost(self, product_id: int, warehouse_id: int = None) -> Decimal:
        """
        Calculate current weighted average cost for a product
        
        Args:
            product_id: Product ID
            warehouse_id: Warehouse ID (optional)
        
        Returns:
            Weighted average unit cost
        """
        layers_query = InventoryCostLayer.objects.filter(
            tenant=self.tenant,
            product_id=product_id,
            quantity_remaining__gt=0,
            is_fully_consumed=False
        )
        
        if warehouse_id:
            layers_query = layers_query.filter(warehouse_id=warehouse_id)
        
        totals = layers_query.aggregate(
            total_quantity=Sum('quantity_remaining'),
            total_cost=Sum(F('quantity_remaining') * F('base_currency_unit_cost'))
        )
        
        total_quantity = totals['total_quantity'] or Decimal('0.00')
        total_cost = totals['total_cost'] or Decimal('0.00')
        
        if total_quantity > 0:
            return total_cost / total_quantity
        return Decimal('0.00')
    
    def get_product_cost_summary(self, product_id: int, warehouse_id: int = None) -> Dict:
        """
        Get comprehensive cost summary for a product
        
        Args:
            product_id: Product ID
            warehouse_id: Warehouse ID (optional)
        
        Returns:
            Cost summary data
        """
        try:
            product = Product.objects.get(id=product_id, tenant=self.tenant)
            
            layers_query = InventoryCostLayer.objects.filter(
                tenant=self.tenant,
                product=product
            )
            
            if warehouse_id:
                warehouse = Warehouse.objects.get(id=warehouse_id, tenant=self.tenant)
                layers_query = layers_query.filter(warehouse=warehouse)
            else:
                warehouse = None
            
            # Active layers (with remaining inventory)
            active_layers = layers_query.filter(
                quantity_remaining__gt=0,
                is_fully_consumed=False
            )
            
            # All layers (for history)
            all_layers = layers_query.all()
            
            # Calculate current inventory value
            current_totals = active_layers.aggregate(
                total_quantity=Sum('quantity_remaining'),
                total_value=Sum(F('quantity_remaining') * F('base_currency_unit_cost')),
                total_with_landed_costs=Sum(
                    F('quantity_remaining') * (F('base_currency_unit_cost') + F('allocated_landed_costs') / F('quantity'))
                )
            )
            
            current_quantity = current_totals['total_quantity'] or Decimal('0.00')
            current_value = current_totals['total_value'] or Decimal('0.00')
            current_value_with_landed = current_totals['total_with_landed_costs'] or Decimal('0.00')
            
            # Calculate costs
            weighted_avg_cost = current_value / current_quantity if current_quantity > 0 else Decimal('0.00')
            effective_avg_cost = current_value_with_landed / current_quantity if current_quantity > 0 else Decimal('0.00')
            
            # Get cost range
            cost_range = active_layers.aggregate(
                min_cost=Min('base_currency_unit_cost'),
                max_cost=Max('base_currency_unit_cost')
            )
            
            # Get latest costs
            latest_layer = active_layers.order_by('-acquisition_date', '-created_date').first()
            latest_cost = latest_layer.base_currency_unit_cost if latest_layer else Decimal('0.00')
            
            # Get oldest costs
            oldest_layer = active_layers.order_by('acquisition_date', 'created_date').first()
            oldest_cost = oldest_layer.base_currency_unit_cost if oldest_layer else Decimal('0.00')
            
            # Historical data
            historical_totals = all_layers.aggregate(
                total_purchased=Sum('quantity', filter=Q(quantity__gt=0)),
                total_consumed=Sum('quantity_consumed', default=Decimal('0.00')),
                total_purchase_value=Sum('base_currency_total_cost', filter=Q(quantity__gt=0)),
                total_landed_costs=Sum('allocated_landed_costs')
            )
            
            return {
                'product': {
                    'id': product.id,
                    'name': product.name,
                    'sku': product.sku
                },
                'warehouse': {
                    'id': warehouse.id,
                    'name': warehouse.name
                } if warehouse else None,
                'current_inventory': {
                    'quantity_on_hand': current_quantity,
                    'inventory_value': current_value,
                    'inventory_value_with_landed_costs': current_value_with_landed,
                    'weighted_average_cost': weighted_avg_cost,
                    'effective_average_cost': effective_avg_cost,
                    'latest_cost': latest_cost,
                    'oldest_cost': oldest_cost,
                    'cost_range': {
                        'minimum': cost_range['min_cost'] or Decimal('0.00'),
                        'maximum': cost_range['max_cost'] or Decimal('0.00')
                    }
                },
                'layer_summary': {
                    'active_layers': active_layers.count(),
                    'total_layers': all_layers.count(),
                    'fully_consumed_layers': all_layers.filter(is_fully_consumed=True).count()
                },
                'historical_data': {
                    'total_purchased': historical_totals['total_purchased'] or Decimal('0.00'),
                    'total_consumed': historical_totals['total_consumed'] or Decimal('0.00'),
                    'total_purchase_value': historical_totals['total_purchase_value'] or Decimal('0.00'),
                    'total_landed_costs': historical_totals['total_landed_costs'] or Decimal('0.00'),
                    'turnover_ratio': (historical_totals['total_consumed'] / current_quantity) if current_quantity > 0 else Decimal('0.00')
                },
                'valuation_method': self.valuation_method,
                'currency': self.base_currency.code,
                'generated_at': timezone.now()
            }
            
        except Product.DoesNotExist:
            raise ValidationError(f"Product {product_id} not found")
        except Warehouse.DoesNotExist:
            raise ValidationError(f"Warehouse {warehouse_id} not found")
    
    def get_inventory_aging_report(self, as_of_date: date = None, 
                                 aging_periods: List[int] = None) -> Dict:
        """
        Generate inventory aging report based on cost layer dates
        
        Args:
            as_of_date: Report date (defaults to today)
            aging_periods: Aging periods in days [30, 60, 90, 180]
        
        Returns:
            Inventory aging report data
        """
        if not as_of_date:
            as_of_date = date.today()
        
        if not aging_periods:
            aging_periods = [30, 60, 90, 180]
        
        # Get all active cost layers
        active_layers = InventoryCostLayer.objects.filter(
            tenant=self.tenant,
            quantity_remaining__gt=0,
            is_fully_consumed=False,
            acquisition_date__lte=as_of_date
        ).select_related('product', 'warehouse')
        
        aging_data = []
        aging_buckets = {
            'current': Decimal('0.00'),
            f'1-{aging_periods[0]}': Decimal('0.00'),
            f'{aging_periods[0]+1}-{aging_periods[1]}': Decimal('0.00'),
            f'{aging_periods[1]+1}-{aging_periods[2]}': Decimal('0.00'),
            f'{aging_periods[2]+1}-{aging_periods[3]}': Decimal('0.00'),
            f'over_{aging_periods[3]}': Decimal('0.00')
        }
        
        for layer in active_layers:
            days_old = (as_of_date - layer.acquisition_date).days
            layer_value = layer.quantity_remaining * layer.effective_unit_cost
            
            # Determine aging bucket
            if days_old <= 0:
                bucket = 'current'
            elif days_old <= aging_periods[0]:
                bucket = f'1-{aging_periods[0]}'
            elif days_old <= aging_periods[1]:
                bucket = f'{aging_periods[0]+1}-{aging_periods[1]}'
            elif days_old <= aging_periods[2]:
                bucket = f'{aging_periods[1]+1}-{aging_periods[2]}'
            elif days_old <= aging_periods[3]:
                bucket = f'{aging_periods[2]+1}-{aging_periods[3]}'
            else:
                bucket = f'over_{aging_periods[3]}'
            
            aging_buckets[bucket] += layer_value
            
            aging_data.append({
                'product_id': layer.product.id,
                'product_name': layer.product.name,
                'product_sku': layer.product.sku,
                'warehouse_id': layer.warehouse.id,
                'warehouse_name': layer.warehouse.name,
                'acquisition_date': layer.acquisition_date,
                'days_old': days_old,
                'quantity_remaining': layer.quantity_remaining,
                'unit_cost': layer.effective_unit_cost,
                'layer_value': layer_value,
                'aging_bucket': bucket,
                'layer_type': layer.layer_type
            })
        
        total_value = sum(aging_buckets.values())
        
        # Calculate percentages
        bucket_percentages = {}
        for bucket, value in aging_buckets.items():
            bucket_percentages[bucket] = (value / total_value * 100) if total_value > 0 else Decimal('0.00')
        
        return {
            'report_name': 'Inventory Aging Report',
            'as_of_date': as_of_date,
            'aging_periods': aging_periods,
            'aging_buckets': aging_buckets,
            'bucket_percentages': bucket_percentages,
            'inventory_details': sorted(aging_data, key=lambda x: x['days_old'], reverse=True),
            'summary': {
                'total_inventory_value': total_value,
                'total_layers': len(aging_data),
                'oldest_inventory_days': max([item['days_old'] for item in aging_data]) if aging_data else 0,
                'average_age_days': sum([item['days_old'] * item['layer_value'] for item in aging_data]) / total_value if total_value > 0 else Decimal('0.00'),
                'slow_moving_value': aging_buckets[f'{aging_periods[2]+1}-{aging_periods[3]}'] + aging_buckets[f'over_{aging_periods[3]}'],
                'slow_moving_percentage': bucket_percentages[f'{aging_periods[2]+1}-{aging_periods[3]}'] + bucket_percentages[f'over_{aging_periods[3]}']
            },
            'currency': self.base_currency.code,
            'generated_at': timezone.now()
        }
    
    def get_cost_variance_analysis(self, product_id: int, start_date: date, 
                                 end_date: date) -> Dict:
        """
        Analyze cost variances for a product over time
        
        Args:
            product_id: Product ID
            start_date: Analysis start date
            end_date: Analysis end date
        
        Returns:
            Cost variance analysis data
        """
        try:
            product = Product.objects.get(id=product_id, tenant=self.tenant)
            
            # Get cost layers within the period
            cost_layers = InventoryCostLayer.objects.filter(
                tenant=self.tenant,
                product=product,
                acquisition_date__gte=start_date,
                acquisition_date__lte=end_date
            ).order_by('acquisition_date')
            
            if not cost_layers.exists():
                return {
                    'product': {'id': product.id, 'name': product.name, 'sku': product.sku},
                    'period': {'start_date': start_date, 'end_date': end_date},
                    'variance_analysis': {
                        'has_data': False,
                        'message': 'No cost layers found for the specified period'
                    }
                }
            
            # Calculate variance metrics
            costs = [layer.base_currency_unit_cost for layer in cost_layers]
            quantities = [layer.quantity for layer in cost_layers]
            
            min_cost = min(costs)
            max_cost = max(costs)
            avg_cost = sum(costs) / len(costs)
            
            # Weighted average cost
            total_value = sum(cost * qty for cost, qty in zip(costs, quantities))
            total_quantity = sum(quantities)
            weighted_avg_cost = total_value / total_quantity if total_quantity > 0 else Decimal('0.00')
            
            # Cost variance
            cost_variance = max_cost - min_cost
            cost_variance_percent = (cost_variance / avg_cost * 100) if avg_cost > 0 else Decimal('0.00')
            
            # Standard deviation
            variance_sum = sum((cost - avg_cost) ** 2 for cost in costs)
            std_deviation = (variance_sum / len(costs)) ** 0.5 if len(costs) > 1 else Decimal('0.00')
            
            # Cost trend analysis
            first_cost = costs[0]
            last_cost = costs[-1]
            cost_trend = ((last_cost - first_cost) / first_cost * 100) if first_cost > 0 else Decimal('0.00')
            
            # Identify volatile periods
            volatile_layers = []
            for i, layer in enumerate(cost_layers[1:], 1):
                prev_cost = costs[i-1]
                current_cost = costs[i]
                change_percent = abs((current_cost - prev_cost) / prev_cost * 100) if prev_cost > 0 else Decimal('0.00')
                
                if change_percent > 10:  # More than 10% change
                    volatile_layers.append({
                        'date': layer.acquisition_date,
                        'previous_cost': prev_cost,
                        'current_cost': current_cost,
                        'change_amount': current_cost - prev_cost,
                        'change_percent': change_percent if current_cost > prev_cost else -change_percent,
                        'layer_type': layer.layer_type,
                        'source_document': layer.source_document_number
                    })
            
            # Monthly cost averages
            monthly_costs = {}
            for layer in cost_layers:
                month_key = layer.acquisition_date.strftime('%Y-%m')
                if month_key not in monthly_costs:
                    monthly_costs[month_key] = {
                        'total_cost': Decimal('0.00'),
                        'total_quantity': Decimal('0.00'),
                        'layer_count': 0
                    }
                
                monthly_costs[month_key]['total_cost'] += layer.base_currency_total_cost
                monthly_costs[month_key]['total_quantity'] += layer.quantity
                monthly_costs[month_key]['layer_count'] += 1
            
            # Calculate monthly averages
            monthly_analysis = []
            for month, data in sorted(monthly_costs.items()):
                avg_monthly_cost = data['total_cost'] / data['total_quantity'] if data['total_quantity'] > 0 else Decimal('0.00')
                monthly_analysis.append({
                    'month': month,
                    'average_cost': avg_monthly_cost,
                    'total_quantity': data['total_quantity'],
                    'total_value': data['total_cost'],
                    'layer_count': data['layer_count']
                })
            
            return {
                'product': {
                    'id': product.id,
                    'name': product.name,
                    'sku': product.sku
                },
                'period': {
                    'start_date': start_date,
                    'end_date': end_date,
                    'days': (end_date - start_date).days + 1
                },
                'variance_analysis': {
                    'has_data': True,
                    'cost_statistics': {
                        'minimum_cost': min_cost,
                        'maximum_cost': max_cost,
                        'average_cost': avg_cost,
                        'weighted_average_cost': weighted_avg_cost,
                        'cost_variance': cost_variance,
                        'cost_variance_percent': cost_variance_percent,
                        'standard_deviation': std_deviation,
                        'coefficient_of_variation': (std_deviation / avg_cost * 100) if avg_cost > 0 else Decimal('0.00')
                    },
                    'trend_analysis': {
                        'first_period_cost': first_cost,
                        'last_period_cost': last_cost,
                        'trend_direction': 'INCREASING' if cost_trend > 0 else 'DECREASING' if cost_trend < 0 else 'STABLE',
                        'trend_percent': cost_trend,
                        'volatility_rating': self._get_volatility_rating(cost_variance_percent)
                    },
                    'volatile_periods': volatile_layers,
                    'monthly_analysis': monthly_analysis,
                    'total_layers_analyzed': len(cost_layers),
                    'total_quantity_analyzed': total_quantity
                },
                'currency': self.base_currency.code,
                'generated_at': timezone.now()
            }
            
        except Product.DoesNotExist:
            raise ValidationError(f"Product {product_id} not found")
    
    def _get_volatility_rating(self, variance_percent: Decimal) -> str:
        """Get volatility rating based on cost variance percentage"""
        if variance_percent <= 5:
            return 'LOW'
        elif variance_percent <= 15:
            return 'MODERATE'
        elif variance_percent <= 30:
            return 'HIGH'
        else:
            return 'VERY_HIGH'
    
    # ============================================================================
    # COST LAYER ADJUSTMENTS & CORRECTIONS
    # ============================================================================
    
    @transaction.atomic
    def adjust_cost_layer(self, layer_id: int, adjustment_data: Dict, user) -> Dict:
        """
        Adjust an existing cost layer
        
        Args:
            layer_id: Cost layer ID to adjust
            adjustment_data: Adjustment details
            user: User making the adjustment
        
        Returns:
            Adjustment result
        """
        try:
            cost_layer = InventoryCostLayer.objects.get(
                id=layer_id,
                tenant=self.tenant
            )
            
            # Store original values
            original_unit_cost = cost_layer.base_currency_unit_cost
            original_total_cost = cost_layer.base_currency_total_cost
            
            # Apply adjustments
            if 'unit_cost' in adjustment_data:
                new_unit_cost = Decimal(str(adjustment_data['unit_cost']))
                cost_layer.base_currency_unit_cost = new_unit_cost
                cost_layer.base_currency_total_cost = cost_layer.quantity * new_unit_cost
            
            if 'landed_cost_adjustment' in adjustment_data:
                landed_cost_adj = Decimal(str(adjustment_data['landed_cost_adjustment']))
                cost_layer.allocated_landed_costs += landed_cost_adj
            
            cost_layer.save()
            
            # Create adjustment journal entry if needed
            adjustment_amount = cost_layer.base_currency_total_cost - original_total_cost
            
            if abs(adjustment_amount) > Decimal('0.01'):
                self._create_cost_adjustment_entry(
                    cost_layer, 
                    adjustment_amount, 
                    adjustment_data.get('reason', 'Cost layer adjustment'),
                    user
                )
            
            logger.info(f"Cost layer {layer_id} adjusted by {adjustment_amount}")
            
            return {
                'success': True,
                'layer_id': layer_id,
                'original_unit_cost': original_unit_cost,
                'new_unit_cost': cost_layer.base_currency_unit_cost,
                'adjustment_amount': adjustment_amount,
                'reason': adjustment_data.get('reason', ''),
                'adjusted_by': user.get_full_name(),
                'adjusted_at': timezone.now()
            }
            
        except InventoryCostLayer.DoesNotExist:
            raise ValidationError(f"Cost layer {layer_id} not found")
        except Exception as e:
            logger.error(f"Error adjusting cost layer: {str(e)}")
            raise ValidationError(f"Failed to adjust cost layer: {str(e)}")
    
    def _create_cost_adjustment_entry(self, cost_layer: InventoryCostLayer, 
                                    adjustment_amount: Decimal, reason: str, user):
        """Create journal entry for cost adjustment"""
        
        inventory_account = self._get_inventory_account()
        adjustment_account = self._get_inventory_adjustment_account()
        
        journal_entry = JournalEntry.objects.create(
            tenant=self.tenant,
            entry_date=date.today(),
            description=f"Cost adjustment - {cost_layer.product.name}",
            entry_type='ADJUSTMENT',
            status='DRAFT',
            currency=self.base_currency,
            exchange_rate=Decimal('1.000000'),
            created_by=user,
            notes=reason
        )
        
        if adjustment_amount > 0:
            # Increase in inventory value
            debit_account = inventory_account
            credit_account = adjustment_account
            debit_amount = adjustment_amount
            credit_amount = adjustment_amount
        else:
            # Decrease in inventory value
            debit_account = adjustment_account
            credit_account = inventory_account
            debit_amount = abs(adjustment_amount)
            credit_amount = abs(adjustment_amount)
        
        # Debit line
        JournalEntryLine.objects.create(
            tenant=self.tenant,
            journal_entry=journal_entry,
            line_number=1,
            account=debit_account,
            description=f"Cost adjustment - {cost_layer.product.name}",
            debit_amount=debit_amount,
            credit_amount=Decimal('0.00'),
            base_currency_debit_amount=debit_amount,
            base_currency_credit_amount=Decimal('0.00'),
            product=cost_layer.product
        )
        
        # Credit line
        JournalEntryLine.objects.create(
            tenant=self.tenant,
            journal_entry=journal_entry,
            line_number=2,
            account=credit_account,
            description=f"Cost adjustment offset - {cost_layer.product.name}",
            debit_amount=Decimal('0.00'),
            credit_amount=credit_amount,
            base_currency_debit_amount=Decimal('0.00'),
            base_currency_credit_amount=credit_amount,
            product=cost_layer.product
        )
        
        journal_entry.calculate_totals()
        journal_entry.post_entry(user)
        
        # Link to cost layer
        cost_layer.journal_entry = journal_entry
        cost_layer.save()
    
    # ============================================================================
    # JOURNAL ENTRY PROCESSING
    # ============================================================================
    
    def process_journal_entry(self, journal_entry: JournalEntry):
        """
        Process journal entry for inventory-related transactions
        
        Args:
            journal_entry: Posted journal entry to process
        """
        if journal_entry.entry_type not in ['INVENTORY', 'ADJUSTMENT', 'COGS']:
            return
        
        try:
            # Process inventory-related journal lines
            inventory_lines = journal_entry.journal_lines.filter(
                account__track_inventory=True
            )
            
            for line in inventory_lines:
                if line.product:
                    # Update inventory cost layers based on journal entry
                    self._update_cost_layers_from_journal_line(line)
            
        except Exception as e:
            logger.error(f"Error processing journal entry {journal_entry.entry_number}: {str(e)}")
    
    def _update_cost_layers_from_journal_line(self, journal_line: JournalEntryLine):
        """Update cost layers based on journal entry line"""
        # This method would handle complex scenarios where journal entries
        # directly affect inventory without going through normal purchase/sale flows
        pass
    
    # ============================================================================
    # HELPER METHODS
    # ============================================================================
    
    def _get_inventory_account(self) -> Account:
        """Get the main inventory account"""
        try:
            return Account.objects.get(
                tenant=self.tenant,
                track_inventory=True,
                account_type='CURRENT_ASSET',
                is_active=True
            )
        except Account.DoesNotExist:
            return Account.objects.create(
                tenant=self.tenant,
                code='1300',
                name='Inventory',
                account_type='CURRENT_ASSET',
                normal_balance='DEBIT',
                currency=self.base_currency,
                track_inventory=True
            )
        except Account.MultipleObjectsReturned:
            return Account.objects.filter(
                tenant=self.tenant,
                track_inventory=True,
                account_type='CURRENT_ASSET',
                is_active=True
            ).first()
    
    def _get_inventory_adjustment_account(self) -> Account:
        """Get the inventory adjustment account"""
        try:
            return Account.objects.get(
                tenant=self.tenant,
                name__icontains='Inventory Adjustment',
                is_active=True
            )
        except Account.DoesNotExist:
            return Account.objects.create(
                tenant=self.tenant,
                code='5200',
                name='Inventory Adjustments',
                account_type='EXPENSE',
                normal_balance='DEBIT',
                currency=self.base_currency
            )
        except Account.MultipleObjectsReturned:
            return Account.objects.filter(
                tenant=self.tenant,
                name__icontains='Inventory Adjustment',
                is_active=True
            ).first()
    
    # ============================================================================
    # VALIDATION & UTILITIES
    # ============================================================================
    
    def validate_cost_layer_integrity(self) -> Dict:
        """
        Validate cost layer data integrity
        
        Returns:
            Validation report
        """
        issues = []
        
        # Check for negative remaining quantities
        negative_layers = InventoryCostLayer.objects.filter(
            tenant=self.tenant,
            quantity_remaining__lt=0
        )
        
        if negative_layers.exists():
            issues.append({
                'type': 'NEGATIVE_INVENTORY',
                'count': negative_layers.count(),
                'description': 'Cost layers with negative remaining quantities found'
            })
        
        # Check for inconsistent consumed flags
        inconsistent_layers = InventoryCostLayer.objects.filter(
            tenant=self.tenant,
            quantity_remaining__gt=0,
            is_fully_consumed=True
        )
        
        if inconsistent_layers.exists():
            issues.append({
                'type': 'INCONSISTENT_FLAGS',
                'count': inconsistent_layers.count(),
                'description': 'Layers marked as consumed but have remaining quantity'
            })
        
        # Check for orphaned consumption records
        orphaned_consumptions = InventoryCostConsumption.objects.filter(
            tenant=self.tenant,
            cost_layer__isnull=True
        )
        
        if orphaned_consumptions.exists():
            issues.append({
                'type': 'ORPHANED_CONSUMPTIONS',
                'count': orphaned_consumptions.count(),
                'description': 'Consumption records without valid cost layers'
            })
        
        return {
            'is_valid': len(issues) == 0,
            'issues_found': len(issues),
            'issues': issues,
            'checked_at': timezone.now()
        }
    
    def reconcile_inventory_values(self, as_of_date: date = None) -> Dict:
        """
        Reconcile inventory values between cost layers and accounting records
        
        Args:
            as_of_date: Reconciliation date
        
        Returns:
            Reconciliation report
        """
        if not as_of_date:
            as_of_date = date.today()
        
        # Calculate inventory value from cost layers
        cost_layer_value = InventoryCostLayer.objects.filter(
            tenant=self.tenant,
            quantity_remaining__gt=0,
            is_fully_consumed=False,
            acquisition_date__lte=as_of_date
        ).aggregate(
            total_value=Sum(F('quantity_remaining') * F('base_currency_unit_cost'))
        )['total_value'] or Decimal('0.00')
        
        # Get inventory account balance
        from .accounting import AccountingService
        accounting_service = AccountingService(self.tenant)
        
        inventory_accounts = Account.objects.filter(
            tenant=self.tenant,
            track_inventory=True,
            is_active=True
        )
        
        accounting_value = Decimal('0.00')
        for account in inventory_accounts:
            balance = accounting_service.get_account_balance(account.id, as_of_date)
            accounting_value += balance
        
        difference = cost_layer_value - accounting_value
        is_reconciled = abs(difference) <= Decimal('0.01')
        
        return {
            'as_of_date': as_of_date,
            'cost_layer_value': cost_layer_value,
            'accounting_value': accounting_value,
            'difference': difference,
            'is_reconciled': is_reconciled,
            'variance_percent': (abs(difference) / accounting_value * 100) if accounting_value > 0 else Decimal('0.00'),
            'currency': self.base_currency.code,
            'reconciled_at': timezone.now()
        }