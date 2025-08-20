# backend/apps/finance/integrations/inventory_integration.py

"""
Finance-Inventory Integration Service
Handles COGS, inventory valuation, and cost layer management
"""

from django.db import transaction
from decimal import Decimal
from datetime import date
from ..models import InventoryCostLayer, JournalEntry, JournalEntryLine
from ..services.journal_entry import JournalEntryService
from ..services.cogs import COGSService

class InventoryIntegrationService:
    """Service for finance-inventory integration"""
    
    def __init__(self, tenant):
        self.tenant = tenant
        self.journal_service = JournalEntryService(tenant)
        self.cogs_service = COGSService(tenant)
    
    @transaction.atomic
    def sync_product_costs(self, product_ids=None):
        """Sync product costs from inventory to finance"""
        from apps.inventory.models import Product, StockItem
        
        products = Product.objects.filter(tenant=self.tenant)
        if product_ids:
            products = products.filter(id__in=product_ids)
        
        sync_results = []
        
        for product in products:
            try:
                # Get current stock items for the product
                stock_items = StockItem.objects.filter(
                    product=product,
                    tenant=self.tenant,
                    quantity_on_hand__gt=0
                )
                
                # Calculate weighted average cost
                total_quantity = sum(item.quantity_on_hand for item in stock_items)
                total_value = sum(
                    item.quantity_on_hand * (item.unit_cost or Decimal('0'))
                    for item in stock_items
                )
                
                if total_quantity > 0:
                    weighted_avg_cost = total_value / total_quantity
                    
                    # Update product cost in inventory
                    product.unit_cost = weighted_avg_cost
                    product.save()
                    
                    sync_results.append({
                        'product_id': product.id,
                        'product_name': product.name,
                        'previous_cost': product.unit_cost,
                        'new_cost': weighted_avg_cost,
                        'status': 'success'
                    })
                
            except Exception as e:
                sync_results.append({
                    'product_id': product.id,
                    'product_name': product.name,
                    'error': str(e),
                    'status': 'error'
                })
        
        return sync_results
    
    @transaction.atomic
    def update_inventory_valuation(self, as_of_date=None):
        """Update inventory valuation in finance"""
        if not as_of_date:
            as_of_date = date.today()
        
        from apps.inventory.models import Product, StockItem
        from ..models import Account
        
        # Get inventory asset account
        inventory_account = Account.objects.filter(
            tenant=self.tenant,
            account_type='CURRENT_ASSET',
            track_inventory=True
        ).first()
        
        if not inventory_account:
            raise ValueError("No inventory asset account found")
        
        # Calculate total inventory value
        total_inventory_value = Decimal('0.00')
        valuation_details = []
        
        products = Product.objects.filter(tenant=self.tenant)
        
        for product in products:
            stock_items = StockItem.objects.filter(
                product=product,
                tenant=self.tenant,
                quantity_on_hand__gt=0
            )
            
            product_value = sum(
                item.quantity_on_hand * (item.unit_cost or Decimal('0'))
                for item in stock_items
            )
            
            total_inventory_value += product_value
            
            if product_value > 0:
                valuation_details.append({
                    'product_id': product.id,
                    'product_name': product.name,
                    'quantity': sum(item.quantity_on_hand for item in stock_items),
                    'value': product_value
                })
        
        # Update inventory account balance
        adjustment_amount = total_inventory_value - inventory_account.current_balance
        
        if abs(adjustment_amount) > Decimal('0.01'):  # Only adjust if significant difference
            # Create inventory valuation adjustment journal entry
            journal_entry = self.journal_service.create_inventory_valuation_adjustment(
                adjustment_amount=adjustment_amount,
                inventory_account=inventory_account,
                as_of_date=as_of_date,
                valuation_details=valuation_details
            )
            
            return {
                'total_inventory_value': total_inventory_value,
                'adjustment_amount': adjustment_amount,
                'journal_entry_id': journal_entry.id,
                'valuation_details': valuation_details
            }
        
        return {
            'total_inventory_value': total_inventory_value,
            'adjustment_amount': Decimal('0.00'),
            'message': 'No adjustment needed',
            'valuation_details': valuation_details
        }
    
    @transaction.atomic
    def create_cogs_entries(self, sale_transactions):
        """Create COGS entries for sales transactions"""
        cogs_entries = []
        
        for transaction in sale_transactions:
            try:
                cogs_entry = self.cogs_service.create_sales_cogs_entry(
                    product_id=transaction['product_id'],
                    quantity_sold=transaction['quantity'],
                    sale_date=transaction['sale_date'],
                    warehouse_id=transaction.get('warehouse_id'),
                    source_document_type=transaction.get('source_type', 'SALE'),
                    source_document_id=transaction.get('source_id')
                )
                
                cogs_entries.append({
                    'transaction_id': transaction.get('id'),
                    'cogs_amount': cogs_entry['cogs_amount'],
                    'journal_entry_id': cogs_entry['journal_entry'].id,
                    'status': 'success'
                })
                
            except Exception as e:
                cogs_entries.append({
                    'transaction_id': transaction.get('id'),
                    'error': str(e),
                    'status': 'error'
                })
        
        return cogs_entries
    
    @transaction.atomic
    def calculate_landed_costs(self, purchase_order_id):
        """Calculate and allocate landed costs"""
        from apps.inventory.models import PurchaseOrder
        from ..models import LandedCost, LandedCostAllocation
        
        try:
            po = PurchaseOrder.objects.get(id=purchase_order_id, tenant=self.tenant)
            
            # Get all cost components for this PO
            freight_costs = po.freight_amount or Decimal('0.00')
            duty_costs = po.duty_amount or Decimal('0.00')
            handling_costs = po.handling_amount or Decimal('0.00')
            
            total_landed_costs = freight_costs + duty_costs + handling_costs
            
            if total_landed_costs <= 0:
                return {'message': 'No landed costs to allocate'}
            
            # Create landed cost record
            landed_cost = LandedCost.objects.create(
                tenant=self.tenant,
                reference_number=f"LC-{po.po_number}",
                description=f"Landed costs for PO {po.po_number}",
                total_landed_cost=total_landed_costs,
                allocation_method='VALUE',
                source_document_type='PURCHASE_ORDER',
                source_document_id=po.id,
                source_purchase_order=po
            )
            
            # Get cost layers for this PO
            cost_layers = InventoryCostLayer.objects.filter(
                tenant=self.tenant,
                source_document_type='PURCHASE_ORDER',
                source_document_id=po.id
            )
            
            total_po_value = sum(layer.base_currency_total_cost for layer in cost_layers)
            
            # Allocate landed costs proportionally
            allocations = []
            for cost_layer in cost_layers:
                if total_po_value > 0:
                    allocation_percentage = (cost_layer.base_currency_total_cost / total_po_value) * 100
                    allocated_amount = (total_landed_costs * allocation_percentage) / 100
                    
                    # Create allocation record
                    allocation = LandedCostAllocation.objects.create(
                        tenant=self.tenant,
                        landed_cost=landed_cost,
                        cost_layer=cost_layer,
                        allocated_amount=allocated_amount,
                        allocation_percentage=allocation_percentage
                    )
                    
                    # Update cost layer with allocated landed costs
                    cost_layer.allocated_landed_costs += allocated_amount
                    cost_layer.save()
                    
                    allocations.append({
                        'cost_layer_id': cost_layer.id,
                        'product_name': cost_layer.product.name,
                        'allocated_amount': allocated_amount,
                        'allocation_percentage': allocation_percentage
                    })
            
            # Mark landed cost as allocated
            landed_cost.is_allocated = True
            landed_cost.allocated_date = timezone.now()
            landed_cost.save()
            
            # Create journal entry for landed costs
            journal_entry = self.journal_service.create_landed_cost_journal_entry(
                landed_cost=landed_cost,
                allocations=allocations
            )
            
            return {
                'landed_cost_id': landed_cost.id,
                'total_allocated': total_landed_costs,
                'allocations': allocations,
                'journal_entry_id': journal_entry.id,
                'status': 'success'
            }
            
        except Exception as e:
            return {
                'error': str(e),
                'status': 'error'
            }