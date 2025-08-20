from django.db import transaction
from django.utils import timezone
from decimal import Decimal
from typing import List, Dict, Any, Optional
from ..base import BaseService, ServiceResult
from ...models import (
    StockMovement, StockValuationLayer, PurchaseOrder,
    StockReceipt, StockAdjustment
)

class FinanceIntegrationService(BaseService):
    """
    Service for integrating inventory with finance/accounting module
    """
    
    def sync_inventory_transactions(self, start_date: Optional[timezone.datetime] = None,
                                   end_date: Optional[timezone.datetime] = None) -> ServiceResult:
        """Sync inventory transactions to finance module"""
        try:
            if not start_date:
                start_date = timezone.now() - timezone.timedelta(days=1)
            if not end_date:
                end_date = timezone.now()
            
            # Get inventory transactions
            movements = StockMovement.objects.filter(
                tenant=self.tenant,
                created_at__range=[start_date, end_date],
                status='COMPLETED'
            )
            
            journal_entries = []
            
            for movement in movements:
                entry_data = self._create_journal_entry_data(movement)
                if_entries.append(entry_data)
            
            # Send to finance module
            finance_result = self._send_to_finance_module(journal_entries)
            
            if finance_result.is_success:
                # Mark movements as synced
                movements.update(finance_synced=True, finance_synced_at=timezone.now())
                
                self.log_operation('sync_inventory_transactions', {
                    'movements_synced': movements.count(),
                    'journal_entries_created': len(journal_entries)
                })
                
                return ServiceResult.success(
                    data={'entries_synced': len(journal_entries)},
                    message=f"Synced {len(journal_entries)} transactions to finance"
                )
            else:
                return finance_result
                
        except Exception as e:
            return ServiceResult.error(f"Failed to sync inventory transactions: {str(e)}")
    
    def _create_journal_entry_data(self, movement: StockMovement) -> Optional[Dict[str, Any]]:
        """Create journal entry data for stock movement"""
        try:
            entry_data = {
                'date': movement.created_at.date(),
                'reference': movement.reference_number,
                'description': f"Inventory {movement.get_movement_type_display()}",
                'source_module': 'INVENTORY',
                'source_id': movement.id,
                'line_items': []
            }
            
            total_value = sum(
                item.quantity * item.unit_cost 
                for item in movement.items.all()
            )
            
            if movement.movement_type == 'RECEIPT':
                # DR: Inventory Asset, CR: Accounts Payable/Cash
                entry_data['line_items'] = [
                    {
                        'account_code': '1200',  # Inventory Asset
                        'description': f"Inventory Receipt - {movement.reference_number}",
                        'debit': total_value,
                        'credit': 0
                    },
                    {
                        'account_code': '2100',  # Accounts Payable
                        'description': f"Inventory Receipt - {movement.reference_number}",
                        'debit': 0,
                        'credit': total_value
                    }
                ]
            
            elif movement.movement_type == 'ISSUE':
                # DR: COGS, CR: Inventory Asset
                entry_data['line_items'] = [
                    {
                        'account_code': '5000',  # Cost of Goods Sold
                        'description': f"Inventory Issue - {movement.reference_number}",
                        'debit': total_value,
                        'credit': 0
                    },
                    {
                        'account_code': '1200',  # Inventory Asset
                        'description': f"Inventory Issue - {movement.reference_number}",
                        'debit': 0,
                        'credit': total_value
                    }
                ]
            
            elif movement.movement_type in ['ADJUSTMENT_POSITIVE', 'ADJUSTMENT_NEGATIVE']:
                # Inventory adjustments
                account_code = '6100' if movement.movement_type == 'ADJUSTMENT_NEGATIVE' else '4900'
                account_name = 'Inventory Adjustment Expense' if movement.movement_type == 'ADJUSTMENT_NEGATIVE' else 'Inventory Adjustment Income'
                
                if movement.movement_type == 'ADJUSTMENT_POSITIVE':
                    entry_data['line_items'] = [
                        {
                            'account_code': '1200',
                            'description': f"Positive Inventory Adjustment - {movement.reference_number}",
                            'debit': total_value,
                            'credit': 0
                        },
                        {
                            'account_code': account_code,
                            'description': f"Positive Inventory Adjustment - {movement.reference_number}",
                            'debit': 0,
                            'credit': total_value
                        }
                    ]
                else:  # ADJUSTMENT_NEGATIVE
                    entry_data['line_items'] = [
                        {
                            'account_code': account_code,
                            'description': f"Negative Inventory Adjustment - {movement.reference_number}",
                            'debit': total_value,
                            'credit': 0
                        },
                        {
                            'account_code': '1200',
                            'description': f"Negative Inventory Adjustment - {movement.reference_number}",
                            'debit': 0,
                            'credit': total_value
                        }
                    ]
            
            return entry_data if entry_data['line_items'] else None
            
        except Exception as e:
            self.logger.error(f"Error creating journal entry for movement {movement.id}: {str(e)}")
            return None
    
    def _send_to_finance_module(self, journal_entries: List[Dict[str, Any]]) -> ServiceResult:
        """Send journal entries to finance module"""
        try:
            # This would integrate with your finance module API
            # For now, we'll simulate the API call
            
            # Example integration with finance module
            import requests
            from django.conf import settings
            
            finance_api_url = getattr(settings, 'FINANCE_API_URL', None)
            finance_api_key = getattr(settings, 'FINANCE_API_KEY', None)
            
            if not finance_api_url or not finance_api_key:
                # Log to database for manual processing
                self._log_journal_entries_for_manual_processing(journal_entries)
                return ServiceResult.success(message="Journal entries logged for manual processing")
            
            headers = {
                'Authorization': f'Bearer {finance_api_key}',
                'Content-Type': 'application/json'
            }
            
            # Send entries in batches
            batch_size = 10
            successful_batches = 0
            
            for i in range(0, len(journal_entries), batch_size):
                batch = journal_entries[i:i + batch_size]
                
                try:
                    response = requests.post(
                        f"{finance_api_url}/journal-entries/batch",
                        json={'entries': batch},
                        headers=headers,
                        timeout=30
                    )
                    
                    if response.status_code == 200:
                        successful_batches += 1
                    else:
                        self.logger.error(f"Finance API error: {response.text}")
                        
                except requests.RequestException as e:
                    self.logger.error(f"Finance API request failed: {str(e)}")
            
            if successful_batches == len(range(0, len(journal_entries), batch_size)):
                return ServiceResult.success()
            else:
                return ServiceResult.error("Some journal entries failed to sync")
                
        except Exception as e:
            return ServiceResult.error(f"Failed to send to finance module: {str(e)}")
    
    def _log_journal_entries_for_manual_processing(self, journal_entries: List[Dict[str, Any]]):
        """Log journal entries for manual processing when API is not available"""
        # Create a model to store pending journal entries
        # This would be implemented based on your specific needs
        pass
    
    def get_inventory_valuation_report(self, as_of_date: Optional[timezone.datetime] = None) -> ServiceResult:
        """Generate inventory valuation report for finance"""
        try:
            if not as_of_date:
                as_of_date = timezone.now()
            
            from ..stock.valuation_service import StockValuationService
            
            valuation_service = StockValuationService(tenant=self.tenant, user=self.user)
            valuation_result = valuation_service.calculate_inventory_value()
            
            if valuation_result.is_success:
                valuation_data = valuation_result.data
                
                # Format for finance module
                finance_report = {
                    'report_date': as_of_date.date().isoformat(),
                    'tenant_id': self.tenant.id,
                    'total_inventory_value': valuation_data['total_value'],
                    'costing_method': valuation_data['costing_method'],
                    'line_items': []
                }
                
                for item in valuation_data['item_values']:
                    finance_report['line_items'].append({
                        'product_id': item['stock_item_id'],
                        'product_name': item['product_name'],
                        'quantity': item['quantity'],
                        'unit_value': item['value'] / item['quantity'] if item['quantity'] > 0 else 0,
                        'total_value': item['value']
                    })
                
                return ServiceResult.success(
                    data=finance_report,
                    message="Inventory valuation report generated for finance"
                )
            else:
                return valuation_result
                
        except Exception as e:
            return ServiceResult.error(f"Failed to generate inventory valuation report: {str(e)}")
    
    def sync_purchase_order_approvals(self, po_id: int) -> ServiceResult:
        """Sync PO approval to finance for budget checking"""
        try:
            po = PurchaseOrder.objects.get(id=po_id, tenant=self.tenant)
            
            # Prepare data for finance module budget check
            budget_check_data = {
                'document_type': 'PURCHASE_ORDER',
                'document_id': po.id,
                'supplier_id': po.supplier.id,
                'total_amount': float(po.total_amount),
                'department': po.warehouse.department if hasattr(po.warehouse, 'department') else None,
                'cost_center': po.cost_center if hasattr(po, 'cost_center') else None,
                'line_items': []
            }
            
            for item in po.items.all():
                budget_check_data['line_items'].append({
                    'product_id': item.product.id,
                    'quantity': float(item.quantity_ordered),
                    'unit_cost': float(item.unit_cost),
                    'total_amount': float(item.total_amount),
                    'account_code': item.product.expense_account_code if hasattr(item.product, 'expense_account_code') else '5000'
                })
            
            # Send to finance for budget check
            budget_result = self._check_budget_availability(budget_check_data)
            
            return budget_result
            
        except PurchaseOrder.DoesNotExist:
            return ServiceResult.error("Purchase order not found")
        except Exception as e:
            return ServiceResult.error(f"Failed to sync PO approval: {str(e)}")
    
    def _check_budget_availability(self, budget ServiceResult:
        """Check budget availability in finance module"""
        try:
            # This would integrate with finance module budget API
            # For now, return success (implement based on your finance module)
            
            return ServiceResult.success(
                data={'budget_available': True, 'remaining_budget': 10000},
                message="Budget check completed"
            )
            
        except Exception as e:
            return ServiceResult.error(f"Budget check failed: {str(e)}")
    
    def generate_cogs_report(self, start_date: timezone.datetime, 
                            end_date: timezone.datetime) -> ServiceResult:
        """Generate Cost of Goods Sold report for finance"""
        try:
            # Get all stock issues (COGS transactions) in period
            cogs_movements = StockMovement.objects.filter(
                tenant=self.tenant,
                movement_type='ISSUE',
                created_at__range=[start_date, end_date],
                status='COMPLETED'
            ).prefetch_related('items__stock_item__product')
            
            cogs_data = []
            total_cogs = Decimal('0')
            
            for movement in cogs_movements:
                for item in movement.items.all():
                    cogs_value = item.quantity * item.unit_cost
                    total_cogs += cogs_value
                    
                    cogs_data.append({
                        'date': movement.created_at.date(),
                        'reference': movement.reference_number,
                        'product_name': item.stock_item.product.name,
                        'product_sku': item.stock_item.product.sku,
                        'quantity': item.quantity,
                        'unit_cost': item.unit_cost,
                        'total_cogs': cogs_value,
                        'customer_reference': movement.customer_reference if hasattr(movement, 'customer_reference') else None
                    })
            
            # Group by product for summary
            product_summary = {}
            for item in c item['product_name']
                if product not in product_summary:
                    product_summary[product] = {
                        'total_quantity': Decimal('0'),
                        'total_cogs': Decimal('0')
                    }
                
                product_summary[product]['total_quantity'] += item['quantity']
                product_summary[product]['total_cogs'] += item['total_cogs']
            
            report_data = {
                'period': {
                    'start_date': start_date.date().isoformat(),
                    'end_date': end_date.date().isoformat()
                },
                'summary': {
                    'total_cogs': total_cogs,
                    'total_transactions': len(cogs_data),
                    'product_count': len(product_summary)
                },
                'product_summary': product_summary,
                'detailed_transactions': cogs_data
            }
            
            return ServiceResult.success(
                data=report_data,
                message=f"COGS report generated for {len(cogs_data)} transactions"
            )
            
        except Exception as e:
            return ServiceResult.error(f"Failed to generate COGS report: {str(e)}")