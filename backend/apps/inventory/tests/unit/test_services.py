# apps/inventory/tests/unit/test_services.py
import pytest
from decimal import Decimal
from unittest.mock import Mock, patch, MagicMock
from django.utils import timezone
from datetime import timedelta

from ...services.stock.movement_service import StockMovementService
from ...services.stock.valuation_service import StockValuationService
from ...services.purchasing.order_service import PurchaseOrderService
from ...services.analytics.abc_service import ABCAnalysisService
from ..factories import *

@pytest.mark.django_db
class TestStockMovementService:
    """Test StockMovementService functionality."""
    
    def test_process_inbound_movement(self, tenant, user):
        """Test processing inbound stock movement."""
        product = ProductFactory(tenant=tenant)
        warehouse = WarehouseFactory(tenant=tenant)
        location = StockLocationFactory(warehouse=warehouse)
        
        # Create initial stock item
        stock_item = StockItemFactory(
            tenant=tenant,
            product=product,
            warehouse=warehouse,
            location=location,
            quantity_on_hand=Decimal('50.0000')
        )
        
        service = StockMovementService(tenant.id)
        
        # Process inbound movement
        result = service.process_movement(
            product_id=product.id,
            warehouse_id=warehouse.id,
            location_id=location.id,
            movement_type='RECEIPT',
            quantity=Decimal('25.0000'),
            unit_cost=Decimal('15.00'),
            reference='PO-001',
            user=user
        )
        
        assert result.success is True
        
        # Check stock item was updated
        stock_item.refresh_from_db()
        assert stock_item.quantity_on_hand == Decimal('75.0000')
        
        # Check movement was recorded
        movement = result.data['movement']
        assert movement.quantity == Decimal('25.0000')
        assert movement.movement_type == 'RECEIPT'
    
    def test_process_outbound_movement_sufficient_stock(self, tenant, user):
        """Test processing outbound movement with sufficient stock."""
        product = ProductFactory(tenant=tenant)
        warehouse = WarehouseFactory(tenant=tenant)
        location = StockLocationFactory(warehouse=warehouse)
        
        # Create stock item with sufficient quantity
        stock_item = StockItemFactory(
            tenant=tenant,
            product=product,
            warehouse=warehouse,
            location=location,
            quantity_on_hand=Decimal('100.0000')
        )
        
        service = StockMovementService(tenant.id)
        
        # Process outbound movement
        result = service.process_movement(
            product_id=product.id,
            warehouse_id=warehouse.id,
            location_id=location.id,
            movement_type='SALE',
            quantity=Decimal('30.0000'),
            unit_cost=Decimal('20.00'),
            reference='SALE-001',
            user=user
        )
        
        assert result.success is True
        
        # Check stock was reduced
        stock_item.refresh_from_db()
        assert stock_item.quantity_on_hand == Decimal('70.0000')
    
    def test_process_outbound_movement_insufficient_stock(self, tenant, user):
        """Test processing outbound movement with insufficient stock."""
        product = ProductFactory(tenant=tenant)
        warehouse = WarehouseFactory(tenant=tenant)
        location = StockLocationFactory(warehouse=warehouse)
        
        # Create stock item with insufficient quantity
        stock_item = StockItemFactory(
            tenant=tenant,
            product=product,
            warehouse=warehouse,
            location=location,
            quantity_on_hand=Decimal('10.0000')
        )
        
        service = StockMovementService(tenant.id)
        
        # Process outbound movement that exceeds available stock
        result = service.process_movement(
            product_id=product.id,
            warehouse_id=warehouse.id,
            location_id=location.id,
            movement_type='SALE',
            quantity=Decimal('50.0000'),
            unit_cost=Decimal('20.00'),
            reference='SALE-002',
            user=user
        )
        
        assert result.success is False
        assert 'insufficient stock' in result.message.lower()
        
        # Check stock wasn't changed
        stock_item.refresh_from_db()
        assert stock_item.quantity_on_hand == Decimal('10.0000')
    
    def test_bulk_movement_processing(self, tenant, user):
        """Test bulk movement processing."""
        products = ProductFactory.create_batch(5, tenant=tenant)
        warehouse = WarehouseFactory(tenant=tenant)
        location = StockLocationFactory(warehouse=warehouse)
        
        # Create stock items
        for product in products:
            StockItemFactory(
                tenant=tenant,
                product=product,
                warehouse=warehouse,
                location=location,
                quantity_on_hand=Decimal('100.0000')
            )
        
        service = StockMovementService(tenant.id)
        
        # Prepare bulk movements
        movements = [
            {
                'product_id': product.id,
                'warehouse_id': warehouse.id,
                'location_id': location.id,
                'movement_type': 'SALE',
                'quantity': Decimal('10.0000'),
                'unit_cost': Decimal('15.00'),
                'reference': f'BULK-{i+1:03d}'
            }
            for i, product in enumerate(products)
        ]
        
        # Process bulk movements
        results = service.process_bulk_movements(movements, user)
        
        assert len(results) == 5
        assert all(result.success for result in results)
        
        # Verify all stock items were updated
        for product in products:
            stock_item = product.stock_items.first()
            assert stock_item.quantity_on_hand == Decimal('90.0000')

@pytest.mark.django_db
class TestStockValuationService:
    """Test StockValuationService functionality."""
    
    def test_fifo_valuation(self, tenant):
        """Test FIFO valuation calculation."""
        product = ProductFactory(tenant=tenant)
        warehouse = WarehouseFactory(tenant=tenant)
        
        service = StockValuationService(tenant.id)
        
        # Create valuation layers (simulating FIFO inventory)
        layers = [
            {'quantity': Decimal('50.0000'), 'unit_cost': Decimal('10.00')},
            {'quantity': Decimal('30.0000'), 'unit_cost': Decimal('12.00')},
            {'quantity': Decimal('20.0000'), 'unit_cost': Decimal('15.00')}
        ]
        
        # Calculate FIFO cost for 60 units
        cost = service.calculate_fifo_cost(layers, Decimal('60.0000'))
        
        # Should take 50 @ $10 + 10 @ $12 = $620
        expected_cost = Decimal('50.0000') * Decimal('10.00') + Decimal('10.0000') * Decimal('12.00')
        assert cost == expected_cost
    
    def test_average_cost_calculation(self, tenant):
        """Test average cost calculation."""
        product = ProductFactory(tenant=tenant)
        warehouse = WarehouseFactory(tenant=tenant)
        
        service = StockValuationService(tenant.id)
        
        # Create movements for average cost calculation
        movements = [
            {'quantity': Decimal('100.0000'), 'unit_cost': Decimal('10.00')},
            {'quantity': Decimal('50.0000'), 'unit_cost': Decimal('12.00')},
            {'quantity': Decimal('25.0000'), 'unit_cost': Decimal('15.00')}
        ]
        
        avg_cost = service.calculate_weighted_average_cost(movements)
        
        # Weighted average: (100*10 + 50*12 + 25*15) / 175 = $11.00
        expected_avg = Decimal('11.00')
        assert abs(avg_cost - expected_avg) < Decimal('0.01')
    
    def test_inventory_valuation_report(self, tenant):
        """Test inventory valuation report generation."""
        # Create test data
        products = ProductFactory.create_batch(3, tenant=tenant)
        warehouse = WarehouseFactory(tenant=tenant)
        
        for i, product in enumerate(products):
            StockItemFactory(
                tenant=tenant,
                product=product,
                warehouse=warehouse,
                quantity_on_hand=Decimal(f'{(i+1)*50}.0000'),
                unit_cost=Decimal(f'{(i+1)*10}.00')
            )
        
        service = StockValuationService(tenant.id)
        
        # Generate valuation report
        report = service.generate_valuation_report(
            warehouse_ids=[warehouse.id]
        )
        
        assert len(report['products']) == 3
        assert report['summary']['total_quantity'] == Decimal('300.0000')
        assert report['summary']['total_value'] > Decimal('0.00')

@pytest.mark.django_db
class TestPurchaseOrderService:
    """Test PurchaseOrderService functionality."""
    
    def test_create_purchase_order(self, tenant, user):
        """Test purchase order creation."""
        supplier = SupplierFactory(tenant=tenant)
        warehouse = WarehouseFactory(tenant=tenant)
        products = ProductFactory.create_batch(3, tenant=tenant)
        
        service = PurchaseOrderService(tenant.id)
        
        # Create PO data
        po_data = {
            'supplier_id': supplier.id,
            'warehouse_id': warehouse.id,
            'expected_delivery_date': timezone.now().date() + timedelta(days=7),
            'items': [
                {
                    'product_id': product.id,
                    'quantity_ordered': Decimal('20.0000'),
                    'unit_cost': Decimal('15.00')
                }
                for product in products
            ]
        }
        
        # Create purchase order
        result = service.create_purchase_order(po_data, user)
        
        assert result.success is True
        
        po = result.data
        assert po.supplier == supplier
        assert po.items.count() == 3
        assert po.total_amount == Decimal('900.00')  # 3 * 20 * 15
    
    def test_purchase_order_approval_workflow(self, tenant, user):
        """Test PO approval workflow."""
        po = PurchaseOrderFactory(
            tenant=tenant,
            status='PENDING_APPROVAL',
            total_amount=Decimal('5000.00')  # Above approval threshold
        )
        
        service = PurchaseOrderService(tenant.id)
        
        # Test approval
        result = service.approve_purchase_order(po.id, user, "Approved for procurement")
        
        assert result.success is True
        
        po.refresh_from_db()
        assert po.status == 'APPROVED'
        assert po.approved_by == user
    
    def test_purchase_order_receipt_processing(self, tenant, user):
        """Test PO receipt processing."""
        po = PurchaseOrderFactory(
            tenant=tenant,
            status='SENT'
        )
        
        # Create PO items
        items = PurchaseOrderItemFactory.create_batch(
            2, 
            tenant=tenant,
            purchase_order=po,
            quantity_ordered=Decimal('10.0000')
        )
        
        service = PurchaseOrderService(tenant.id)
        
        # Process receipt
        receipt_data = {
            'purchase_order_id': po.id,
            'items': [
                {
                    'purchase_order_item_id': item.id,
                    'quantity_received': Decimal('8.0000'),  # Partial receipt
                    'condition': 'GOOD'
                }
                for item in items
            ]
        }
        
        result = service.process_receipt(receipt_data, user)
        
        assert result.success is True
        
        # Check PO status updated
        po.refresh_from_db()
        assert po.status == 'PARTIALLY_RECEIVED'

@pytest.mark.django_db  
class TestABCAnalysisService:
    """Test ABC Analysis Service functionality."""
    
    def test_abc_classification_by_sales_value(self, tenant):
        """Test ABC classification based on sales value."""
        # Create products with different sales values
        products = []
        for i in range(10):
            product = ProductFactory(
                tenant=tenant,
                cost_price=Decimal(f'{50 + i * 10}.00'),
                selling_price=Decimal(f'{75 + i * 15}.00')
            )
            
            # Create movements to simulate sales
            StockMovementFactory.create_batch(
                i + 1,  # More movements for higher-indexed products
                tenant=tenant,
                product=product,
                movement_type='SALE',
                quantity=Decimal('10.0000'),
                unit_cost=product.cost_price
            )
            products.append(product)
        
        service = ABCAnalysisService(tenant.id)
        
        # Run ABC analysis
        result = service.run_abc_analysis(
            analysis_method='SALES_VALUE',
            class_a_threshold=80.0,
            class_b_threshold=95.0
        )
        
        assert result.success is True
        
        analysis_data = result.data
        assert len(analysis_data['products']) == 10
        
        # Check that products are classified
        class_counts = {
            'A': sum(1 for p in analysis_data['products'] if p['classification'] == 'A'),
            'B': sum(1 for p in analysis_data['products'] if p['classification'] == 'B'),
            'C': sum(1 for p in analysis_data['products'] if p['classification'] == 'C')
        }
        
        assert class_counts['A'] > 0
        assert class_counts['B'] > 0
        assert class_counts['C'] > 0
    
    def test_pareto_analysis_calculation(self, tenant):
        """Test Pareto analysis calculations."""
        # Create test data with known values
        data = [
            {'value': 1000, 'product_id': 1},
            {'value': 800, 'product_id': 2},
            {'value': 600, 'product_id': 3},
            {'value': 400, 'product_id': 4},
            {'value': 200, 'product_id': 5}
        ]
        
        service = ABCAnalysisService(tenant.id)
        
        # Calculate Pareto analysis
        result = service.calculate_pareto_analysis(data)
        
        assert len(result) == 5
        
        # Check cumulative percentages
        total_value = sum(item['value'] for item in data)
        cumulative = 0
        
        for item in result:
            cumulative += item['value']
            expected_percentage = (cumulative / total_value) * 100
            assert abs(item['cumulative_percentage'] - expected_percentage) < 0.01