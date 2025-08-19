"""
Finance Services - Cost of Goods Sold (COGS) Service
Advanced COGS calculation with FIFO, LIFO, and Weighted Average methods
"""

from django.db import transaction, models
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.db.models import Sum, F, Q, Case, When, DecimalField
from decimal import Decimal, ROUND_HALF_UP
from datetime import date, datetime, timedelta
import logging
from typing import Dict, List, Optional, Tuple, Any

from apps.core.utils import generate_code
from ..models import (
    Account, JournalEntry, JournalEntryLine, InventoryCostLayer, 
    InventoryCostConsumption, Invoice, InvoiceItem, Bill, BillItem,
    Product, Warehouse, FinanceSettings, Currency
)


logger = logging.getLogger(__name__)


class COGSService:
    """Cost of Goods Sold calculation service with multiple valuation methods"""
    
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
    # MAIN COGS ENTRY POINTS
    # ============================================================================
    
    @transaction.atomic
    def create_invoice_cogs_entries(self, invoice) -> List[JournalEntry]:
        """
        Create COGS journal entries for invoice line items
        
        Args:
            invoice: Invoice instance
        
        Returns:
            List of created COGS journal entries
        """
        if not self.settings.auto_create_cogs_entries:
            logger.info(f"Auto COGS entries disabled for tenant {self.tenant}")
            return []
        
        try:
            cogs_entries = []
            
            # Process each product line item
            product_items = invoice.invoice_items.filter(
                item_type='PRODUCT',
                product__isnull=False,
                quantity__gt=0
            )
            
            if not product_items.exists():
                logger.info(f"No product items found for invoice {invoice.invoice_number}")
                return []
            
            # Group items by product and warehouse for efficiency
            grouped_items = self._group_invoice_items(product_items)
            
            for (product_id, warehouse_id), items in grouped_items.items():
                total_quantity = sum(item.quantity for item in items)
                
                # Calculate COGS for this product/warehouse combination
                cogs_data = self.calculate_product_cogs(
                    product_id=product_id,
                    warehouse_id=warehouse_id,
                    quantity_sold=total_quantity,
                    sale_date=invoice.invoice_date
                )
                
                if cogs_data['total_cost'] > Decimal('0.00'):
                    # Create COGS journal entry
                    cogs_entry = self._create_cogs_journal_entry(
                        invoice=invoice,
                        product_id=product_id,
                        warehouse_id=warehouse_id,
                        cogs_data=cogs_data,
                        items=items
                    )
                    
                    if cogs_entry:
                        cogs_entries.append(cogs_entry)
                        
                        # Update cost layers
                        self._update_cost_layers_for_sale(cogs_data['cost_layers_consumed'])
            
            logger.info(f"Created {len(cogs_entries)} COGS entries for invoice {invoice.invoice_number}")
            return cogs_entries
            
        except Exception as e:
            logger.error(f"Error creating COGS entries for invoice {invoice.invoice_number}: {str(e)}")
            raise ValidationError(f"Failed to create COGS entries: {str(e)}")
    
    @transaction.atomic
    def create_bill_cogs_entries(self, bill) -> List[JournalEntry]:
        """
        Create inventory cost layer entries when receiving goods via bills
        
        Args:
            bill: Bill instance
        
        Returns:
            List of created inventory journal entries
        """
        try:
            inventory_entries = []
            
            # Process each product line item
            product_items = bill.bill_items.filter(
                item_type='PRODUCT',
                product__isnull=False,
                quantity__gt=0
            )
            
            if not product_items.exists():
                logger.info(f"No product items found for bill {bill.bill_number}")
                return []
            
            for item in product_items:
                # Create cost layer for received inventory
                cost_layer = self._create_inventory_cost_layer(
                    bill_item=item,
                    bill=bill
                )
                
                # Create inventory journal entry
                inventory_entry = self._create_inventory_receipt_entry(
                    bill=bill,
                    bill_item=item,
                    cost_layer=cost_layer
                )
                
                if inventory_entry:
                    inventory_entries.append(inventory_entry)
            
            logger.info(f"Created {len(inventory_entries)} inventory entries for bill {bill.bill_number}")
            return inventory_entries
            
        except Exception as e:
            logger.error(f"Error creating inventory entries for bill {bill.bill_number}: {str(e)}")
            raise ValidationError(f"Failed to create inventory entries: {str(e)}")
    
    # ============================================================================
    # COGS CALCULATION METHODS
    # ============================================================================
    
    def calculate_product_cogs(self, product_id: int, warehouse_id: int, 
                             quantity_sold: Decimal, sale_date: date = None) -> Dict:
        """
        Calculate COGS for a product sale using configured valuation method
        
        Args:
            product_id: Product ID
            warehouse_id: Warehouse ID  
            quantity_sold: Quantity being sold
            sale_date: Date of sale (defaults to today)
        
        Returns:
            Dictionary with COGS calculation details
        """
        if not sale_date:
            sale_date = date.today()
        
        if self.valuation_method == 'FIFO':
            return self._calculate_fifo_cogs(product_id, warehouse_id, quantity_sold, sale_date)
        elif self.valuation_method == 'LIFO':
            return self._calculate_lifo_cogs(product_id, warehouse_id, quantity_sold, sale_date)
        elif self.valuation_method == 'WEIGHTED_AVERAGE':
            return self._calculate_weighted_average_cogs(product_id, warehouse_id, quantity_sold, sale_date)
        elif self.valuation_method == 'SPECIFIC_ID':
            return self._calculate_specific_id_cogs(product_id, warehouse_id, quantity_sold, sale_date)
        else:
            # Default to FIFO
            return self._calculate_fifo_cogs(product_id, warehouse_id, quantity_sold, sale_date)
    
    def _calculate_fifo_cogs(self, product_id: int, warehouse_id: int, 
                           quantity_sold: Decimal, sale_date: date) -> Dict:
        """Calculate COGS using First-In-First-Out method"""
        
        # Get available cost layers ordered by acquisition date (oldest first)
        available_layers = InventoryCostLayer.objects.filter(
            tenant=self.tenant,
            product_id=product_id,
            warehouse_id=warehouse_id,
            quantity_remaining__gt=0,
            acquisition_date__lte=sale_date,
            is_fully_consumed=False
        ).order_by('acquisition_date', 'created_date')
        
        return self._consume_cost_layers(available_layers, quantity_sold, 'FIFO')
    
    def _calculate_lifo_cogs(self, product_id: int, warehouse_id: int, 
                           quantity_sold: Decimal, sale_date: date) -> Dict:
        """Calculate COGS using Last-In-First-Out method"""
        
        # Get available cost layers ordered by acquisition date (newest first)
        available_layers = InventoryCostLayer.objects.filter(
            tenant=self.tenant,
            product_id=product_id,
            warehouse_id=warehouse_id,
            quantity_remaining__gt=0,
            acquisition_date__lte=sale_date,
            is_fully_consumed=False
        ).order_by('-acquisition_date', '-created_date')
        
        return self._consume_cost_layers(available_layers, quantity_sold, 'LIFO')
    
    def _calculate_weighted_average_cogs(self, product_id: int, warehouse_id: int, 
                                       quantity_sold: Decimal, sale_date: date) -> Dict:
        """Calculate COGS using Weighted Average method"""
        
        # Get all available cost layers
        available_layers = InventoryCostLayer.objects.filter(
            tenant=self.tenant,
            product_id=product_id,
            warehouse_id=warehouse_id,
            quantity_remaining__gt=0,
            acquisition_date__lte=sale_date,
            is_fully_consumed=False
        )
        
        if not available_layers.exists():
            return self._create_empty_cogs_result()
        
        # Calculate weighted average unit cost
        totals = available_layers.aggregate(
            total_quantity=Sum('quantity_remaining'),
            total_cost=Sum(F('quantity_remaining') * F('base_currency_unit_cost'))
        )
        
        total_quantity = totals['total_quantity'] or Decimal('0.00')
        total_cost = totals['total_cost'] or Decimal('0.00')
        
        if total_quantity <= 0:
            return self._create_empty_cogs_result()
        
        weighted_avg_unit_cost = total_cost / total_quantity
        
        # Check if we have enough inventory
        if quantity_sold > total_quantity:
            raise ValidationError(
                f"Insufficient inventory. Available: {total_quantity}, Requested: {quantity_sold}"
            )
        
        # For weighted average, we consume proportionally from all layers
        cost_layers_consumed = []
        remaining_quantity = quantity_sold
        total_cogs_cost = Decimal('0.00')
        
        for layer in available_layers:
            if remaining_quantity <= 0:
                break
            
            # Calculate proportion of this layer to consume
            layer_proportion = layer.quantity_remaining / total_quantity
            quantity_to_consume = min(
                quantity_sold * layer_proportion,
                layer.quantity_remaining,
                remaining_quantity
            )
            
            if quantity_to_consume > 0:
                layer_cost = quantity_to_consume * weighted_avg_unit_cost
                
                cost_layers_consumed.append({
                    'layer': layer,
                    'quantity_consumed': quantity_to_consume,
                    'unit_cost': weighted_avg_unit_cost,
                    'total_cost': layer_cost
                })
                
                total_cogs_cost += layer_cost
                remaining_quantity -= quantity_to_consume
        
        return {
            'total_cost': total_cogs_cost,
            'average_unit_cost': weighted_avg_unit_cost,
            'quantity_sold': quantity_sold,
            'cost_layers_consumed': cost_layers_consumed,
            'valuation_method': 'WEIGHTED_AVERAGE'
        }
    
    def _calculate_specific_id_cogs(self, product_id: int, warehouse_id: int, 
                                  quantity_sold: Decimal, sale_date: date) -> Dict:
        """Calculate COGS using Specific Identification method"""
        # This would require additional logic to specify which exact units are being sold
        # For now, fall back to FIFO
        logger.warning("Specific ID costing not fully implemented, falling back to FIFO")
        return self._calculate_fifo_cogs(product_id, warehouse_id, quantity_sold, sale_date)
    
    def _consume_cost_layers(self, available_layers, quantity_sold: Decimal, method: str) -> Dict:
        """Common method to consume cost layers for FIFO/LIFO"""
        
        if not available_layers.exists():
            return self._create_empty_cogs_result()
        
        # Check if we have enough inventory
        total_available = available_layers.aggregate(
            total=Sum('quantity_remaining')
        )['total'] or Decimal('0.00')
        
        if quantity_sold > total_available:
            raise ValidationError(
                f"Insufficient inventory. Available: {total_available}, Requested: {quantity_sold}"
            )
        
        cost_layers_consumed = []
        remaining_quantity = quantity_sold
        total_cost = Decimal('0.00')
        
        for layer in available_layers:
            if remaining_quantity <= 0:
                break
            
            quantity_to_consume = min(layer.quantity_remaining, remaining_quantity)
            layer_cost = quantity_to_consume * layer.effective_unit_cost
            
            cost_layers_consumed.append({
                'layer': layer,
                'quantity_consumed': quantity_to_consume,
                'unit_cost': layer.effective_unit_cost,
                'total_cost': layer_cost
            })
            
            total_cost += layer_cost
            remaining_quantity -= quantity_to_consume
        
        # Calculate weighted average unit cost for this sale
        avg_unit_cost = total_cost / quantity_sold if quantity_sold > 0 else Decimal('0.00')
        
        return {
            'total_cost': total_cost,
            'average_unit_cost': avg_unit_cost,
            'quantity_sold': quantity_sold,
            'cost_layers_consumed': cost_layers_consumed,
            'valuation_method': method
        }
    
    def _create_empty_cogs_result(self) -> Dict:
        """Create empty COGS result when no inventory available"""
        return {
            'total_cost': Decimal('0.00'),
            'average_unit_cost': Decimal('0.00'),
            'quantity_sold': Decimal('0.00'),
            'cost_layers_consumed': [],
            'valuation_method': self.valuation_method
        }
    
    # ============================================================================
    # JOURNAL ENTRY CREATION
    # ============================================================================
    
    def _create_cogs_journal_entry(self, invoice, product_id: int, warehouse_id: int,
                                 cogs_data: Dict, items: List) -> JournalEntry:
        """Create COGS journal entry"""
        
        try:
            product = Product.objects.get(id=product_id, tenant=self.tenant)
            warehouse = Warehouse.objects.get(id=warehouse_id, tenant=self.tenant)
            
            # Get COGS and Inventory accounts
            cogs_account = self._get_cogs_account()
            inventory_account = self._get_inventory_account()
            
            # Create journal entry
            journal_entry = JournalEntry.objects.create(
                tenant=self.tenant,
                entry_date=invoice.invoice_date,
                description=f"COGS - {product.name} ({invoice.invoice_number})",
                entry_type='COGS',
                status='DRAFT',
                currency=invoice.currency,
                exchange_rate=invoice.exchange_rate,
                source_document_type='INVOICE',
                source_document_id=invoice.id,
                source_document_number=invoice.invoice_number,
                created_by=invoice.created_by
            )
            
            line_number = 1
            
            # Debit: Cost of Goods Sold
            JournalEntryLine.objects.create(
                tenant=self.tenant,
                journal_entry=journal_entry,
                line_number=line_number,
                account=cogs_account,
                description=f"COGS - {product.name}",
                debit_amount=cogs_data['total_cost'],
                credit_amount=Decimal('0.00'),
                base_currency_debit_amount=cogs_data['total_cost'],
                base_currency_credit_amount=Decimal('0.00'),
                customer=invoice.customer,
                product=product,
                quantity=cogs_data['quantity_sold'],
                unit_cost=cogs_data['average_unit_cost']
            )
            line_number += 1
            
            # Credit: Inventory
            JournalEntryLine.objects.create(
                tenant=self.tenant,
                journal_entry=journal_entry,
                line_number=line_number,
                account=inventory_account,
                description=f"Inventory reduction - {product.name}",
                debit_amount=Decimal('0.00'),
                credit_amount=cogs_data['total_cost'],
                base_currency_debit_amount=Decimal('0.00'),
                base_currency_credit_amount=cogs_data['total_cost'],
                customer=invoice.customer,
                product=product,
                quantity=cogs_data['quantity_sold'],
                unit_cost=cogs_data['average_unit_cost']
            )
            
            # Calculate totals and post
            journal_entry.calculate_totals()
            journal_entry.post_entry(invoice.created_by)
            
            logger.info(f"COGS journal entry {journal_entry.entry_number} created for {product.name}")
            return journal_entry
            
        except Exception as e:
            logger.error(f"Error creating COGS journal entry: {str(e)}")
            raise ValidationError(f"Failed to create COGS journal entry: {str(e)}")
    
    def _create_inventory_receipt_entry(self, bill, bill_item, cost_layer) -> JournalEntry:
        """Create journal entry for inventory receipt"""
        
        try:
            # Get Inventory and AP accounts
            inventory_account = self._get_inventory_account()
            ap_account = self._get_accounts_payable_account()
            
            # Create journal entry
            journal_entry = JournalEntry.objects.create(
                tenant=self.tenant,
                entry_date=bill.bill_date,
                description=f"Inventory Receipt - {bill_item.product.name} ({bill.bill_number})",
                entry_type='INVENTORY',
                status='DRAFT',
                currency=bill.currency,
                exchange_rate=bill.exchange_rate,
                source_document_type='BILL',
                source_document_id=bill.id,
                source_document_number=bill.bill_number,
                created_by=bill.created_by
            )
            
            line_number = 1
            inventory_value = bill_item.quantity * bill_item.unit_cost
            
            # Debit: Inventory
            JournalEntryLine.objects.create(
                tenant=self.tenant,
                journal_entry=journal_entry,
                line_number=line_number,
                account=inventory_account,
                description=f"Inventory receipt - {bill_item.product.name}",
                debit_amount=inventory_value,
                credit_amount=Decimal('0.00'),
                base_currency_debit_amount=inventory_value * bill.exchange_rate,
                base_currency_credit_amount=Decimal('0.00'),
                vendor=bill.vendor,
                product=bill_item.product,
                quantity=bill_item.quantity,
                unit_cost=bill_item.unit_cost
            )
            line_number += 1
            
            # Credit: Accounts Payable (this will be offset by the main bill entry)
            JournalEntryLine.objects.create(
                tenant=self.tenant,
                journal_entry=journal_entry,
                line_number=line_number,
                account=ap_account,
                description=f"Inventory payable - {bill.vendor.company_name}",
                debit_amount=Decimal('0.00'),
                credit_amount=inventory_value,
                base_currency_debit_amount=Decimal('0.00'),
                base_currency_credit_amount=inventory_value * bill.exchange_rate,
                vendor=bill.vendor,
                product=bill_item.product
            )
            
            # Calculate totals and post
            journal_entry.calculate_totals()
            journal_entry.post_entry(bill.created_by)
            
            # Link to cost layer
            cost_layer.journal_entry = journal_entry
            cost_layer.save()
            
            logger.info(f"Inventory receipt entry {journal_entry.entry_number} created")
            return journal_entry
            
        except Exception as e:
            logger.error(f"Error creating inventory receipt entry: {str(e)}")
            raise ValidationError(f"Failed to create inventory receipt entry: {str(e)}")
    
    # ============================================================================
    # COST LAYER MANAGEMENT
    # ============================================================================
    
    def _create_inventory_cost_layer(self, bill_item, bill) -> InventoryCostLayer:
        """Create inventory cost layer for received goods"""
        
        try:
            # Calculate base currency unit cost
            base_currency_unit_cost = bill_item.unit_cost * bill.exchange_rate
            total_cost = bill_item.quantity * bill_item.unit_cost
            base_currency_total_cost = total_cost * bill.exchange_rate
            
            cost_layer = InventoryCostLayer.objects.create(
                tenant=self.tenant,
                product=bill_item.product,
                warehouse=bill_item.warehouse,
                layer_type='PURCHASE',
                quantity=bill_item.quantity,
                unit_cost=bill_item.unit_cost,
                total_cost=total_cost,
                currency=bill.currency,
                exchange_rate=bill.exchange_rate,
                base_currency_unit_cost=base_currency_unit_cost,
                base_currency_total_cost=base_currency_total_cost,
                source_document_type='BILL',
                source_document_id=bill.id,
                source_document_number=bill.bill_number,
                acquisition_date=bill.bill_date,
                quantity_remaining=bill_item.quantity
            )
            
            logger.info(f"Cost layer created for {bill_item.product.name}: {bill_item.quantity} @ {bill_item.unit_cost}")
            return cost_layer
            
        except Exception as e:
            logger.error(f"Error creating cost layer: {str(e)}")
            raise ValidationError(f"Failed to create cost layer: {str(e)}")
    
    def _update_cost_layers_for_sale(self, cost_layers_consumed: List[Dict]):
        """Update cost layers after sale consumption"""
        
        for layer_data in cost_layers_consumed:
            layer = layer_data['layer']
            quantity_consumed = layer_data['quantity_consumed']
            
            # Create consumption record
            InventoryCostConsumption.objects.create(
                tenant=self.tenant,
                cost_layer=layer,
                quantity_consumed=quantity_consumed,
                unit_cost=layer_data['unit_cost'],
                total_cost=layer_data['total_cost'],
                consumption_date=date.today()
            )
            
            # Update layer remaining quantity
            layer.quantity_remaining -= quantity_consumed
            
            if layer.quantity_remaining <= Decimal('0.0001'):  # Essentially zero
                layer.quantity_remaining = Decimal('0.00')
                layer.is_fully_consumed = True
            
            layer.save()
    
    # ============================================================================
    # INVENTORY VALUATION
    # ============================================================================
    
    def calculate_inventory_valuation(self, as_of_date: date = None, 
                                    warehouse_id: int = None) -> Dict:
        """
        Calculate total inventory valuation as of a specific date
        
        Args:
            as_of_date: Date for valuation (defaults to today)
            warehouse_id: Specific warehouse (optional)
        
        Returns:
            Inventory valuation data
        """
        if not as_of_date:
            as_of_date = date.today()
        
        # Build query for cost layers
        layers_query = InventoryCostLayer.objects.filter(
            tenant=self.tenant,
            quantity_remaining__gt=0,
            acquisition_date__lte=as_of_date
        )
        
        if warehouse_id:
            layers_query = layers_query.filter(warehouse_id=warehouse_id)
        
        # Group by product and warehouse
        valuation_data = []
        
        products_warehouses = layers_query.values(
            'product_id', 'warehouse_id'
        ).distinct()
        
        total_valuation = Decimal('0.00')
        
        for pw in products_warehouses:
            product_layers = layers_query.filter(
                product_id=pw['product_id'],
                warehouse_id=pw['warehouse_id']
            )
            
            # Calculate valuation based on method
            if self.valuation_method == 'WEIGHTED_AVERAGE':
                valuation = self._calculate_weighted_avg_valuation(product_layers)
            else:
                # For FIFO/LIFO, valuation is sum of remaining cost layers
                valuation = product_layers.aggregate(
                    total_value=Sum(F('quantity_remaining') * F('base_currency_unit_cost'))
                )['total_value'] or Decimal('0.00')
            
            if valuation > Decimal('0.00'):
                product = Product.objects.get(id=pw['product_id'])
                warehouse = Warehouse.objects.get(id=pw['warehouse_id'])
                
                total_quantity = product_layers.aggregate(
                    total=Sum('quantity_remaining')
                )['total'] or Decimal('0.00')
                
                avg_unit_cost = valuation / total_quantity if total_quantity > 0 else Decimal('0.00')
                
                valuation_data.append({
                    'product_id': product.id,
                    'product_name': product.name,
                    'product_sku': product.sku,
                    'warehouse_id': warehouse.id,
                    'warehouse_name': warehouse.name,
                    'quantity_on_hand': total_quantity,
                    'average_unit_cost': avg_unit_cost,
                    'total_value': valuation
                })
                
                total_valuation += valuation
        
        return {
            'as_of_date': as_of_date,
            'valuation_method': self.valuation_method,
            'currency': self.base_currency.code,
            'total_inventory_value': total_valuation,
            'products': sorted(valuation_data, key=lambda x: x['product_name']),
            'summary': {
                'total_products': len(valuation_data),
                'total_quantity': sum(item['quantity_on_hand'] for item in valuation_data),
                'average_value_per_product': total_valuation / len(valuation_data) if valuation_data else Decimal('0.00')
            },
            'generated_at': timezone.now()
        }
    
    def _calculate_weighted_avg_valuation(self, product_layers) -> Decimal:
        """Calculate weighted average valuation for product layers"""
        totals = product_layers.aggregate(
            total_quantity=Sum('quantity_remaining'),
            total_cost=Sum(F('quantity_remaining') * F('base_currency_unit_cost'))
        )
        
        return totals['total_cost'] or Decimal('0.00')
    
    # ============================================================================
    # COGS ANALYSIS & REPORTING
    # ============================================================================
    
    def get_cogs_analysis(self, start_date: date, end_date: date, 
                         product_id: int = None) -> Dict:
        """
        Analyze COGS for a period
        
        Args:
            start_date: Analysis period start
            end_date: Analysis period end
            product_id: Specific product (optional)
        
        Returns:
            COGS analysis data
        """
        # Get COGS journal entries for period
        cogs_entries = JournalEntry.objects.filter(
            tenant=self.tenant,
            entry_type='COGS',
            entry_date__gte=start_date,
            entry_date__lte=end_date,
            status='POSTED'
        )
        
        if product_id:
            cogs_entries = cogs_entries.filter(
                journal_lines__product_id=product_id
            )
        
        # Analyze COGS by product
        product_analysis = {}
        total_cogs = Decimal('0.00')
        total_quantity = Decimal('0.00')
        
        for entry in cogs_entries:
            cogs_lines = entry.journal_lines.filter(
                account__account_type='COST_OF_GOODS_SOLD',
                debit_amount__gt=0
            )
            
            for line in cogs_lines:
                if line.product:
                    product_key = line.product.id
                    
                    if product_key not in product_analysis:
                        product_analysis[product_key] = {
                            'product_id': line.product.id,
                            'product_name': line.product.name,
                            'product_sku': line.product.sku,
                            'total_cogs': Decimal('0.00'),
                            'total_quantity': Decimal('0.00'),
                            'average_unit_cost': Decimal('0.00'),
                            'transaction_count': 0
                        }
                    
                    product_analysis[product_key]['total_cogs'] += line.base_currency_debit_amount
                    product_analysis[product_key]['total_quantity'] += line.quantity or Decimal('0.00')
                    product_analysis[product_key]['transaction_count'] += 1
                    
                    total_cogs += line.base_currency_debit_amount
                    total_quantity += line.quantity or Decimal('0.00')
        
        # Calculate average unit costs
        for data in product_analysis.values():
            if data['total_quantity'] > 0:
                data['average_unit_cost'] = data['total_cogs'] / data['total_quantity']
        
        overall_avg_cost = total_cogs / total_quantity if total_quantity > 0 else Decimal('0.00')
        
        return {
            'period': {
                'start_date': start_date,
                'end_date': end_date
            },
            'summary': {
                'total_cogs': total_cogs,
                'total_quantity_sold': total_quantity,
                'average_unit_cost': overall_avg_cost,
                'total_transactions': sum(data['transaction_count'] for data in product_analysis.values())
            },
            'products': sorted(product_analysis.values(), key=lambda x: x['total_cogs'], reverse=True),
            'currency': self.base_currency.code,
            'valuation_method': self.valuation_method,
            'generated_at': timezone.now()
        }
    
    def get_gross_margin_analysis(self, start_date: date, end_date: date) -> Dict:
        """
        Analyze gross margins by product for a period
        
        Args:
            start_date: Analysis period start
            end_date: Analysis period end
        
        Returns:
            Gross margin analysis data
        """
        # Get invoice items for period
        invoice_items = InvoiceItem.objects.filter(
            tenant=self.tenant,
            invoice__status__in=['PAID', 'PARTIAL', 'OPEN'],
            invoice__invoice_date__gte=start_date,
            invoice__invoice_date__lte=end_date,
            item_type='PRODUCT',
            product__isnull=False
        ).select_related('product', 'invoice')
        
        # Get corresponding COGS entries
        cogs_entries = JournalEntry.objects.filter(
            tenant=self.tenant,
            entry_type='COGS',
            entry_date__gte=start_date,
            entry_date__lte=end_date,
            status='POSTED'
        ).prefetch_related('journal_lines__product')
        
        # Build COGS lookup by product and date
        cogs_lookup = {}
        for entry in cogs_entries:
            for line in entry.journal_lines.filter(account__account_type='COST_OF_GOODS_SOLD'):
                if line.product:
                    key = (line.product.id, entry.entry_date)
                    if key not in cogs_lookup:
                        cogs_lookup[key] = {'total_cogs': Decimal('0.00'), 'total_quantity': Decimal('0.00')}
                    
                    cogs_lookup[key]['total_cogs'] += line.base_currency_debit_amount
                    cogs_lookup[key]['total_quantity'] += line.quantity or Decimal('0.00')
        
        # Analyze margins by product
        margin_analysis = {}
        
        for item in invoice_items:
            product_key = item.product.id
            
            if product_key not in margin_analysis:
                margin_analysis[product_key] = {
                    'product_id': item.product.id,
                    'product_name': item.product.name,
                    'product_sku': item.product.sku,
                    'total_revenue': Decimal('0.00'),
                    'total_cogs': Decimal('0.00'),
                    'total_quantity': Decimal('0.00'),
                    'gross_profit': Decimal('0.00'),
                    'gross_margin_percent': Decimal('0.00'),
                    'average_selling_price': Decimal('0.00'),
                    'average_cost': Decimal('0.00'),
                    'transaction_count': 0
                }
            
            # Add revenue
            revenue = item.line_total * item.invoice.exchange_rate  # Convert to base currency
            margin_analysis[product_key]['total_revenue'] += revenue
            margin_analysis[product_key]['total_quantity'] += item.quantity
            margin_analysis[product_key]['transaction_count'] += 1
            
            # Find corresponding COGS
            cogs_key = (item.product.id, item.invoice.invoice_date)
            if cogs_key in cogs_lookup:
                # Allocate COGS proportionally
                cogs_data = cogs_lookup[cogs_key]
                if cogs_data['total_quantity'] > 0:
                    unit_cogs = cogs_data['total_cogs'] / cogs_data['total_quantity']
                    allocated_cogs = unit_cogs * item.quantity
                    margin_analysis[product_key]['total_cogs'] += allocated_cogs
        
        # Calculate margins and averages
        for data in margin_analysis.values():
            data['gross_profit'] = data['total_revenue'] - data['total_cogs']
            
            if data['total_revenue'] > 0:
                data['gross_margin_percent'] = (data['gross_profit'] / data['total_revenue']) * 100
            
            if data['total_quantity'] > 0:
                data['average_selling_price'] = data['total_revenue'] / data['total_quantity']
                data['average_cost'] = data['total_cogs'] / data['total_quantity']
        
        # Calculate overall totals
        total_revenue = sum(data['total_revenue'] for data in margin_analysis.values())
        total_cogs = sum(data['total_cogs'] for data in margin_analysis.values())
        total_gross_profit = total_revenue - total_cogs
        overall_margin = (total_gross_profit / total_revenue * 100) if total_revenue > 0 else Decimal('0.00')
        
        return {
            'period': {
                'start_date': start_date,
                'end_date': end_date
            },
            'summary': {
                'total_revenue': total_revenue,
                'total_cogs': total_cogs,
                'total_gross_profit': total_gross_profit,
                'overall_gross_margin_percent': overall_margin,
                'products_analyzed': len(margin_analysis)
            },
            'products': sorted(margin_analysis.values(), key=lambda x: x['gross_profit'], reverse=True),
            'top_performers': sorted(
                [p for p in margin_analysis.values() if p['gross_margin_percent'] > 0],
                key=lambda x: x['gross_margin_percent'], reverse=True
            )[:10],
            'poor_performers': sorted(
                [p for p in margin_analysis.values() if p['gross_margin_percent'] < 10],
                key=lambda x: x['gross_margin_percent']
            )[:10],
            'currency': self.base_currency.code,
            'generated_at': timezone.now()
        }
    
    # ============================================================================
    # INVENTORY TURNOVER ANALYSIS
    # ============================================================================
    
    def calculate_inventory_turnover(self, start_date: date, end_date: date, 
                                   product_id: int = None) -> Dict:
        """
        Calculate inventory turnover metrics
        
        Args:
            start_date: Period start date
            end_date: Period end date
            product_id: Specific product (optional)
        
        Returns:
            Inventory turnover analysis
        """
        # Get COGS for the period
        cogs_analysis = self.get_cogs_analysis(start_date, end_date, product_id)
        
        # Get average inventory value during period
        # Calculate at beginning and end of period, then average
        beginning_inventory = self.calculate_inventory_valuation(start_date)
        ending_inventory = self.calculate_inventory_valuation(end_date)
        
        if product_id:
            # Filter for specific product
            beginning_value = sum(
                item['total_value'] for item in beginning_inventory['products']
                if item['product_id'] == product_id
            )
            ending_value = sum(
                item['total_value'] for item in ending_inventory['products']
                if item['product_id'] == product_id
            )
        else:
            beginning_value = beginning_inventory['total_inventory_value']
            ending_value = ending_inventory['total_inventory_value']
        
        average_inventory = (beginning_value + ending_value) / 2
        total_cogs = cogs_analysis['summary']['total_cogs']
        
        # Calculate turnover metrics
        days_in_period = (end_date - start_date).days + 1
        
        if average_inventory > 0:
            inventory_turnover = total_cogs / average_inventory
            days_in_inventory = days_in_period / inventory_turnover
        else:
            inventory_turnover = Decimal('0.00')
            days_in_inventory = Decimal('0.00')
        
        # Annual turnover (extrapolated)
        annual_turnover = inventory_turnover * (365 / days_in_period)
        
        return {
            'period': {
                'start_date': start_date,
                'end_date': end_date,
                'days': days_in_period
            },
            'inventory_values': {
                'beginning_inventory': beginning_value,
                'ending_inventory': ending_value,
                'average_inventory': average_inventory
            },
            'turnover_metrics': {
                'cogs_for_period': total_cogs,
                'inventory_turnover_ratio': inventory_turnover,
                'days_in_inventory': days_in_inventory,
                'annual_turnover_ratio': annual_turnover
            },
            'interpretation': {
                'turnover_rating': self._interpret_turnover_ratio(annual_turnover),
                'efficiency_notes': self._get_turnover_efficiency_notes(days_in_inventory)
            },
            'currency': self.base_currency.code,
            'generated_at': timezone.now()
        }
    
    def _interpret_turnover_ratio(self, turnover_ratio: Decimal) -> str:
        """Interpret inventory turnover ratio"""
        if turnover_ratio >= 12:
            return 'Excellent (12+ times per year)'
        elif turnover_ratio >= 8:
            return 'Good (8-12 times per year)'
        elif turnover_ratio >= 4:
            return 'Fair (4-8 times per year)'
        elif turnover_ratio >= 2:
            return 'Poor (2-4 times per year)'
        else:
            return 'Very Poor (less than 2 times per year)'
    
    def _get_turnover_efficiency_notes(self, days_in_inventory: Decimal) -> str:
        """Get efficiency notes based on days in inventory"""
        if days_in_inventory <= 30:
            return 'Very efficient inventory management'
        elif days_in_inventory <= 60:
            return 'Good inventory management'
        elif days_in_inventory <= 90:
            return 'Average inventory management'
        elif days_in_inventory <= 180:
            return 'Slow-moving inventory - consider review'
        else:
            return 'Very slow-moving inventory - immediate attention required'
    
    # ============================================================================
    # HELPER METHODS
    # ============================================================================
    
    def _group_invoice_items(self, invoice_items):
        """Group invoice items by product and warehouse"""
        grouped = {}
        
        for item in invoice_items:
            warehouse_id = item.warehouse.id if item.warehouse else None
            key = (item.product.id, warehouse_id)
            
            if key not in grouped:
                grouped[key] = []
            
            grouped[key].append(item)
        
        return grouped
    
    def _get_cogs_account(self) -> Account:
        """Get the Cost of Goods Sold account"""
        try:
            return Account.objects.get(
                tenant=self.tenant,
                account_type='COST_OF_GOODS_SOLD',
                is_active=True
            )
        except Account.DoesNotExist:
            # Create default COGS account
            return Account.objects.create(
                tenant=self.tenant,
                code='5000',
                name='Cost of Goods Sold',
                account_type='COST_OF_GOODS_SOLD',
                normal_balance='DEBIT',
                currency=self.base_currency
            )
        except Account.MultipleObjectsReturned:
            # Return the first COGS account
            return Account.objects.filter(
                tenant=self.tenant,
                account_type='COST_OF_GOODS_SOLD',
                is_active=True
            ).first()
    
    def _get_inventory_account(self) -> Account:
        """Get the Inventory asset account"""
        try:
            return Account.objects.get(
                tenant=self.tenant,
                track_inventory=True,
                account_type='CURRENT_ASSET',
                is_active=True
            )
        except Account.DoesNotExist:
            # Create default inventory account
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
            # Return the first inventory account
            return Account.objects.filter(
                tenant=self.tenant,
                track_inventory=True,
                account_type='CURRENT_ASSET',
                is_active=True
            ).first()
    
    def _get_accounts_payable_account(self) -> Account:
        """Get the Accounts Payable account"""
        try:
            return Account.objects.get(
                tenant=self.tenant,
                account_type='CURRENT_LIABILITY',
                name__icontains='Accounts Payable',
                is_active=True
            )
        except Account.DoesNotExist:
            # Create default A/P account
            return Account.objects.create(
                tenant=self.tenant,
                code='2000',
                name='Accounts Payable',
                account_type='CURRENT_LIABILITY',
                normal_balance='CREDIT',
                currency=self.base_currency
            )
        except Account.MultipleObjectsReturned:
            return Account.objects.filter(
                tenant=self.tenant,
                account_type='CURRENT_LIABILITY',
                name__icontains='Accounts Payable',
                is_active=True
            ).first()
    
    # ============================================================================
    # VALIDATION & UTILITIES
    # ============================================================================
    
    def validate_inventory_availability(self, product_id: int, warehouse_id: int, 
                                      quantity_needed: Decimal, 
                                      as_of_date: date = None) -> Dict:
        """
        Validate if sufficient inventory is available for sale
        
        Args:
            product_id: Product ID
            warehouse_id: Warehouse ID
            quantity_needed: Quantity to validate
            as_of_date: Date to check availability
        
        Returns:
            Validation result with availability details
        """
        if not as_of_date:
            as_of_date = date.today()
        
        # Get available cost layers
        available_layers = InventoryCostLayer.objects.filter(
            tenant=self.tenant,
            product_id=product_id,
            warehouse_id=warehouse_id,
            quantity_remaining__gt=0,
            acquisition_date__lte=as_of_date,
            is_fully_consumed=False
        )
        
        total_available = available_layers.aggregate(
            total=Sum('quantity_remaining')
        )['total'] or Decimal('0.00')
        
        is_available = total_available >= quantity_needed
        shortage = max(Decimal('0.00'), quantity_needed - total_available)
        
        # Get layer details
        layer_details = []
        for layer in available_layers.order_by('acquisition_date'):
            layer_details.append({
                'layer_id': layer.id,
                'acquisition_date': layer.acquisition_date,
                'quantity_remaining': layer.quantity_remaining,
                'unit_cost': layer.effective_unit_cost,
                'source_document': layer.source_document_number
            })
        
        return {
            'is_available': is_available,
            'quantity_needed': quantity_needed,
            'quantity_available': total_available,
            'shortage': shortage,
            'availability_layers': layer_details,
            'total_layers': len(layer_details),
            'valuation_method': self.valuation_method,
            'as_of_date': as_of_date
        }
    
    def recalculate_product_costs(self, product_id: int, 
                                warehouse_id: int = None) -> Dict:
        """
        Recalculate costs for a product (useful after cost adjustments)
        
        Args:
            product_id: Product ID to recalculate
            warehouse_id: Specific warehouse (optional)
        
        Returns:
            Recalculation results
        """
        try:
            with transaction.atomic():
                # Get cost layers to recalculate
                layers_query = InventoryCostLayer.objects.filter(
                    tenant=self.tenant,
                    product_id=product_id
                )
                
                if warehouse_id:
                    layers_query = layers_query.filter(warehouse_id=warehouse_id)
                
                layers_updated = 0
                total_adjustments = Decimal('0.00')
                
                for layer in layers_query:
                    # Recalculate effective unit cost including landed costs
                    old_cost = layer.effective_unit_cost
                    
                    if layer.quantity > 0:
                        new_unit_cost = (layer.base_currency_total_cost + layer.allocated_landed_costs) / layer.quantity
                        
                        if new_unit_cost != old_cost:
                            # Update the layer
                            layer.base_currency_unit_cost = new_unit_cost
                            layer.save()
                            
                            adjustment = (new_unit_cost - old_cost) * layer.quantity_remaining
                            total_adjustments += adjustment
                            layers_updated += 1
                
                return {
                    'success': True,
                    'product_id': product_id,
                    'warehouse_id': warehouse_id,
                    'layers_updated': layers_updated,
                    'total_cost_adjustment': total_adjustments,
                    'recalculated_at': timezone.now()
                }
                
        except Exception as e:
            logger.error(f"Error recalculating product costs: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'product_id': product_id,
                'warehouse_id': warehouse_id
            }
    
    def get_cost_layer_history(self, product_id: int, warehouse_id: int = None, 
                             limit: int = 50) -> Dict:
        """
        Get cost layer history for a product
        
        Args:
            product_id: Product ID
            warehouse_id: Warehouse ID (optional)
            limit: Number of records to return
        
        Returns:
            Cost layer history data
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
            
            layers = layers_query.order_by('-acquisition_date', '-created_date')[:limit]
            
            # Get consumption history
            consumption_query = InventoryCostConsumption.objects.filter(
                tenant=self.tenant,
                cost_layer__product=product
            )
            
            if warehouse_id:
                consumption_query = consumption_query.filter(cost_layer__warehouse_id=warehouse_id)
            
            consumptions = consumption_query.order_by('-consumption_date')[:limit]
            
            # Format layer data
            layer_data = []
            for layer in layers:
                layer_data.append({
                    'layer_id': layer.id,
                    'acquisition_date': layer.acquisition_date,
                    'layer_type': layer.layer_type,
                    'source_document': layer.source_document_number,
                    'original_quantity': layer.quantity,
                    'quantity_remaining': layer.quantity_remaining,
                    'unit_cost': layer.unit_cost,
                    'base_currency_unit_cost': layer.base_currency_unit_cost,
                    'effective_unit_cost': layer.effective_unit_cost,
                    'total_cost': layer.total_cost,
                    'is_fully_consumed': layer.is_fully_consumed,
                    'warehouse_name': layer.warehouse.name if layer.warehouse else None
                })
            
            # Format consumption data
            consumption_data = []
            for consumption in consumptions:
                consumption_data.append({
                    'consumption_date': consumption.consumption_date,
                    'quantity_consumed': consumption.quantity_consumed,
                    'unit_cost': consumption.unit_cost,
                    'total_cost': consumption.total_cost,
                    'source_document': consumption.source_document_type,
                    'layer_acquisition_date': consumption.cost_layer.acquisition_date,
                    'warehouse_name': consumption.cost_layer.warehouse.name if consumption.cost_layer.warehouse else None
                })
            
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
                'cost_layers': layer_data,
                'consumption_history': consumption_data,
                'summary': {
                    'total_layers': len(layer_data),
                    'active_layers': len([l for l in layer_data if not l['is_fully_consumed']]),
                    'total_on_hand': sum(l['quantity_remaining'] for l in layer_data),
                    'total_value': sum(l['quantity_remaining'] * l['effective_unit_cost'] for l in layer_data)
                },
                'valuation_method': self.valuation_method,
                'generated_at': timezone.now()
            }
            
        except Product.DoesNotExist:
            raise ValidationError(f"Product {product_id} not found")
        except Warehouse.DoesNotExist:
            raise ValidationError(f"Warehouse {warehouse_id} not found")
        except Exception as e:
            logger.error(f"Error getting cost layer history: {str(e)}")
            raise ValidationError(f"Failed to get cost layer history: {str(e)}")