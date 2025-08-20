# apps/inventory/api/v1/serializers/purchasing.py

from rest_framework import serializers
from decimal import Decimal
from django.utils import timezone
from django.db import transaction
from apps.inventory.models.purchasing import PurchaseOrder, PurchaseOrderItem, StockReceipt, StockReceiptItem
from apps.inventory.models.suppliers.suppliers import Supplier
from apps.inventory.models.warehouse.warehouses import Warehouse
from .base import AuditableSerializer, DynamicFieldsSerializer, NestedCreateUpdateSerializer
from .catalog import ProductSerializer
from .core import SupplierSerializer

class PurchaseOrderItemSerializer(serializers.ModelSerializer):
    """Serializer for purchase order items."""
    
    product_name = serializers.CharField(source='product.name', read_only=True)
    product_sku = serializers.CharField(source='product.sku', read_only=True)
    uom_name = serializers.CharField(source='product.uom.name', read_only=True)
    line_total = serializers.SerializerMethodField()
    received_quantity = serializers.SerializerMethodField()
    pending_quantity = serializers.SerializerMethodField()
    receipt_status = serializers.SerializerMethodField()
    
    class Meta:
        model = PurchaseOrderItem
        fields = [
            'id', 'product', 'product_name', 'product_sku', 'uom_name',
            'quantity', 'unit_price', 'discount_percentage', 'discount_amount',
            'line_total', 'tax_percentage', 'tax_amount', 'notes',
            'received_quantity', 'pending_quantity', 'receipt_status',
            'expected_delivery_date'
        ]
        read_only_fields = [
            'line_total', 'received_quantity', 'pending_quantity', 'receipt_status'
        ]
    
    def get_line_total(self, obj):
        """Calculate line total including tax and discount."""
        subtotal = obj.quantity * obj.unit_price
        discount = obj.discount_amount or (subtotal * (obj.discount_percentage or 0) / 100)
        after_discount = subtotal - discount
        tax = obj.tax_amount or (after_discount * (obj.tax_percentage or 0) / 100)
        return after_discount + tax
    
    def get_received_quantity(self, obj):
        """Get total received quantity for this item."""
        return sum(
            receipt_item.quantity_received 
            for receipt_item in obj.receipt_items.all()
        )
    
    def get_pending_quantity(self, obj):
        """Calculate pending quantity to be received."""
        received = self.get_received_quantity(obj)
        return max(0, obj.quantity - received)
    
    def get_receipt_status(self, obj):
        """Determine receipt status for this item."""
        received = self.get_received_quantity(obj)
        
        if received == 0:
            return 'PENDING'
        elif received < obj.quantity:
            return 'PARTIAL'
        elif received == obj.quantity:
            return 'COMPLETE'
        else:
            return 'OVER_RECEIVED'
    
    def validate_quantity(self, value):
        """Validate order quantity."""
        if value <= 0:
            raise serializers.ValidationError("Quantity must be greater than 0")
        return value
    
    def validate_unit_price(self, value):
        """Validate unit price."""
        if value < 0:
            raise serializers.ValidationError("Unit price cannot be negative")
        return value
    
    def validate_discount_percentage(self, value):
        """Validate discount percentage."""
        if value is not None and (value < 0 or value > 100):
            raise serializers.ValidationError("Discount percentage must be between 0 and 100")
        return value
    
    def validate_tax_percentage(self, value):
        """Validate tax percentage."""
        if value is not None and (value < 0 or value > 100):
            raise serializers.ValidationError("Tax percentage must be between 0 and 100")
        return value
    
    def validate(self, data):
        """Cross-field validation."""
        # Ensure either discount_percentage or discount_amount is provided, not both
        discount_percentage = data.get('discount_percentage')
        discount_amount = data.get('discount_amount')
        
        if discount_percentage is not None and discount_amount is not None:
            raise serializers.ValidationError(
                "Provide either discount_percentage or discount_amount, not both"
            )
        
        # Same for tax
        tax_percentage = data.get('tax_percentage')
        tax_amount = data.get('tax_amount')
        
        if tax_percentage is not None and tax_amount is not None:
            raise serializers.ValidationError(
                "Provide either tax_percentage or tax_amount, not both"
            )
        
        return data

class PurchaseOrderSerializer(AuditableSerializer, DynamicFieldsSerializer):
    """Main purchase order serializer."""
    
    supplier = SupplierSerializer(read_only=True)
    supplier_id = serializers.IntegerField(write_only=True)
    warehouse_name = serializers.CharField(source='warehouse.name', read_only=True)
    items = PurchaseOrderItemSerializer(many=True, read_only=True)
    
    # Calculated fields
    subtotal = serializers.SerializerMethodField()
    total_discount = serializers.SerializerMethodField()
    total_tax = serializers.SerializerMethodField()
    total_amount = serializers.SerializerMethodField()
    item_count = serializers.SerializerMethodField()
    
    # Status information
    receipt_status = serializers.SerializerMethodField()
    approval_status = serializers.SerializerMethodField()
    days_since_order = serializers.SerializerMethodField()
    is_overdue = serializers.SerializerMethodField()
    
    # Approval information
    approved_by_name = serializers.CharField(source='approved_by.get_full_name', read_only=True, allow_null=True)
    
    class Meta:
        model = PurchaseOrder
        fields = [
            'id', 'order_number', 'supplier', 'supplier_id', 'warehouse', 'warehouse_name',
            'order_date', 'expected_delivery_date', 'status', 'priority',
            'payment_terms', 'shipping_terms', 'notes', 'internal_notes',
            'subtotal', 'total_discount', 'total_tax', 'total_amount',
            'requires_approval', 'approved_by', 'approved_by_name', 'approved_at',
            'items', 'item_count', 'receipt_status', 'approval_status',
            'days_since_order', 'is_overdue',
            'created_at', 'updated_at', 'created_by'
        ]
        read_only_fields = [
            'order_number', 'subtotal', 'total_discount', 'total_tax', 
            'total_amount', 'item_count', 'receipt_status', 'approval_status',
            'days_since_order', 'is_overdue'
        ]
    
    def get_subtotal(self, obj):
        """Calculate subtotal before discount and tax."""
        return sum(item.quantity * item.unit_price for item in obj.items.all())
    
    def get_total_discount(self, obj):
        """Calculate total discount amount."""
        total = Decimal('0')
        for item in obj.items.all():
            if item.discount_amount:
                total += item.discount_amount
            elif item.discount_percentage:
                line_subtotal = item.quantity * item.unit_price
                total += line_subtotal * (item.discount_percentage / 100)
        return total
    
    def get_total_tax(self, obj):
        """Calculate total tax amount."""
        total = Decimal('0')
        for item in obj.items.all():
            if item.tax_amount:
                total += item.tax_amount
            elif item.tax_percentage:
                line_subtotal = item.quantity * item.unit_price
                discount = item.discount_amount or (line_subtotal * (item.discount_percentage or 0) / 100)
                taxable_amount = line_subtotal - discount
                total += taxable_amount * (item.tax_percentage / 100)
        return total
    
    def get_total_amount(self, obj):
        """Calculate total order amount."""
        subtotal = self.get_subtotal(obj)
        discount = self.get_total_discount(obj)
        tax = self.get_total_tax(obj)
        return subtotal - discount + tax
    
    def get_item_count(self, obj):
        """Get number of items in order."""
        return obj.items.count()
    
    def get_receipt_status(self, obj):
        """Determine overall receipt status."""
        if not obj.items.exists():
            return 'NO_ITEMS'
        
        total_ordered = sum(item.quantity for item in obj.items.all())
        total_received = sum(
            sum(receipt_item.quantity_received for receipt_item in item.receipt_items.all())
            for item in obj.items.all()
        )
        
        if total_received == 0:
            return 'PENDING'
        elif total_received < total_ordered:
            return 'PARTIAL'
        else:
            return 'COMPLETE'
    
    def get_approval_status(self, obj):
        """Get approval status."""
        if not obj.requires_approval:
            return 'NOT_REQUIRED'
        elif obj.approved_at:
            return 'APPROVED'
        else:
            return 'PENDING'
    
    def get_days_since_order(self, obj):
        """Calculate days since order was placed."""
        return (timezone.now().date() - obj.order_date).days
    
    def get_is_overdue(self, obj):
        """Check if order is overdue for delivery."""
        if not obj.expected_delivery_date:
            return False
        return obj.expected_delivery_date < timezone.now().date() and obj.status != 'COMPLETED'
    
    def validate_expected_delivery_date(self, value):
        """Validate expected delivery date."""
        if value and value < timezone.now().date():
            raise serializers.ValidationError("Expected delivery date cannot be in the past")
        return value
    
    def validate_supplier_id(self, value):
        """Validate supplier exists and is active."""
        try:
            supplier = Supplier.objects.get(
                id=value,
                tenant=self.context['request'].user.tenant,
                is_active=True
            )
        except Supplier.DoesNotExist:
            raise serializers.ValidationError("Invalid or inactive supplier")
        return value

class PurchaseOrderDetailSerializer(PurchaseOrderSerializer):
    """Detailed purchase order serializer with additional information."""
    
    receipt_history = serializers.SerializerMethodField()
    approval_history = serializers.SerializerMethodField()
    delivery_performance = serializers.SerializerMethodField()
    
    class Meta(PurchaseOrderSerializer.Meta):
        fields = PurchaseOrderSerializer.Meta.fields + [
            'receipt_history', 'approval_history', 'delivery_performance'
        ]
    
    def get_receipt_history(self, obj):
        """Get receipt history for this order."""
        receipts = obj.receipts.select_related('warehouse', 'received_by').order_by('-received_date')
        
        return [
            {
                'id': receipt.id,
                'receipt_number': receipt.receipt_number,
                'received_date': receipt.received_date,
                'warehouse': receipt.warehouse.name,
                'received_by': receipt.received_by.get_full_name() if receipt.received_by else None,
                'status': receipt.status,
                'item_count': receipt.items.count(),
                'total_quantity_received': sum(item.quantity_received for item in receipt.items.all())
            }
            for receipt in receipts
        ]
    
    def get_approval_history(self, obj):
        """Get approval history."""
        # This would include approval workflow history
        history = []
        if obj.approved_at:
            history.append({
                'action': 'APPROVED',
                'user': obj.approved_by.get_full_name() if obj.approved_by else None,
                'timestamp': obj.approved_at,
                'notes': 'Purchase order approved'
            })
        return history
    
    def get_delivery_performance(self, obj):
        """Calculate delivery performance metrics."""
        receipts = obj.receipts.all()
        
        if not receipts.exists():
            return {
                'status': 'NO_DELIVERIES',
                'on_time_delivery': None,
                'days_early_late': None
            }
        
        first_receipt = receipts.order_by('received_date').first()
        expected_date = obj.expected_delivery_date
        
        if not expected_date:
            return {
                'status': 'NO_EXPECTED_DATE',
                'on_time_delivery': None,
                'days_early_late': None
            }
        
        days_difference = (first_receipt.received_date - expected_date).days
        
        return {
            'status': 'DELIVERED',
            'on_time_delivery': days_difference <= 0,
            'days_early_late': days_difference,
            'first_delivery_date': first_receipt.received_date
        }

class PurchaseOrderCreateSerializer(NestedCreateUpdateSerializer):
    """Serializer for creating purchase orders with items."""
    
    items = PurchaseOrderItemSerializer(many=True)
    
    class Meta:
        model = PurchaseOrder
        fields = [
            'supplier', 'warehouse', 'order_date', 'expected_delivery_date',
            'priority', 'payment_terms', 'shipping_terms', 'notes',
            'internal_notes', 'items'
        ]
    
    def create(self, validated_data):
        """Create purchase order with items."""
        items_data = validated_data.pop('items')
        
        # Set tenant and auto-generate order number
        validated_data['tenant'] = self.context['request'].user.tenant
        validated_data['created_by'] = self.context['request'].user
        
        with transaction.atomic():
            # Create purchase order
            purchase_order = PurchaseOrder.objects.create(**validated_data)
            
            # Create items
            fordata['purchase_order'] = purchase_order
                PurchaseOrderItem.objects.create(**item_data)
        
        return purchase_order
    
    def validate_items(self, value):
        """Validate purchase order items."""
        if not value:
            raise serializers.ValidationError("Purchase order must have at least one item")
        
        if len(value) > 100:  # Reasonable limit
            raise serializers.ValidationError("Purchase order cannot have more than 100 items")
        
        # Check for duplicate products
        product_ids = [item.get('product').id if item.get('product') else None for item in value]
        if len(product_ids) != len(set(product_ids)):
            raise serializers.ValidationError("Duplicate products found in order items")
        
        return value

class PurchaseOrderApprovalSerializer(serializers.Serializer):
    """Serializer for purchase order approval/rejection."""
    
    action = serializers.ChoiceField(choices=['approve', 'reject'])
    notes = serializers.CharField(required=False, allow_blank=True)
    reason = serializers.CharField(required=False, allow_blank=True)
    
    def validate(self, data):
        """Validate approval data."""
        if data['action'] == 'reject' and not data.get('reason'):
            raise serializers.ValidationError(
                "Reason is required when rejecting a purchase order"
            )
        return data

class StockReceiptItemSerializer(serializers.ModelSerializer):
    """Serializer for stock receipt items."""
    
    product_name = serializers.CharField(source='product.name', read_only=True)
    product_sku = serializers.CharField(source='product.sku', read_only=True)
    ordered_quantity = serializers.SerializerMethodField()
    variance_quantity = serializers.SerializerMethodField()
    variance_percentage = serializers.SerializerMethodField()
    line_value = serializers.SerializerMethodField()
    
    class Meta:
        model = StockReceiptItem
        fields = [
            'id', 'product', 'product_name', 'product_sku',
            'purchase_order_item', 'ordered_quantity', 'quantity_received',
            'quantity_damaged', 'variance_quantity', 'variance_percentage',
            'unit_cost', 'line_value', 'batch', 'expiry_date',
            'quality_check_passed', 'notes'
        ]
        read_only_fields = [
            'ordered_quantity', 'variance_quantity', 'variance_percentage', 'line_value'
        ]
    
    def get_ordered_quantity(self, obj):
        """Get originally ordered quantity."""
        return obj.purchase_order_item.quantity if obj.purchase_order_item else 0
    
    def get_variance_quantity(self, obj):
        """Calculate quantity variance."""
        ordered = self.get_ordered_quantity(obj)
        return obj.quantity_received - ordered
    
    def get_variance_percentage(self, obj):
        """Calculate variance percentage."""
        ordered = self.get_ordered_quantity(obj)
        if ordered == 0:
            return None
        
        variance = self.get_variance_quantity(obj)
        return (variance / ordered) * 100
    
    def get_line_value(self, obj):
        """Calculate line value."""
        return obj.quantity_received * obj.unit_cost
    
    def validate_quantity_received(self, value):
        """Validate received quantity."""
        if value < 0:
            raise serializers.ValidationError("Received quantity cannot be negative")
        return value
    
    def validate_quantity_damaged(self, value):
        """Validate damaged quantity."""
        if value < 0:
            raise serializers.ValidationError("Damaged quantity cannot be negative")
        return value
    
    def validate(self, data):
        """Cross-field validation."""
        quantity_received = data.get('quantity_received', 0)
        quantity_damaged = data.get('quantity_damaged', 0)
        
        if quantity_damaged > quantity_received:
            raise serializers.ValidationError(
                "Damaged quantity cannot exceed received quantity"
            )
        
        return data

class StockReceiptSerializer(AuditableSerializer, DynamicFieldsSerializer):
    """Serializer for stock receipts."""
    
    purchase_order_number = serializers.CharField(source='purchase_order.order_number', read_only=True)
    supplier_name = serializers.CharField(source='purchase_order.supplier.name', read_only=True)
    warehouse_name = serializers.CharField(source='warehouse.name', read_only=True)
    received_by_name = serializers.CharField(source='received_by.get_full_name', read_only=True, allow_null=True)
    
    items = StockReceiptItemSerializer(many=True, read_only=True)
    
    # Calculated fields
    total_quantity_received = serializers.SerializerMethodField()
    total_quantity_damaged = serializers.SerializerMethodField()
    total_value = serializers.SerializerMethodField()
    item_count = serializers.SerializerMethodField()
    quality_pass_rate = serializers.SerializerMethodField()
    
    class Meta:
        model = StockReceipt
        fields = [
            'id', 'receipt_number', 'purchase_order', 'purchase_order_number',
            'supplier_name', 'warehouse', 'warehouse_name',
            'received_date', 'received_by', 'received_by_name',
            'status', 'quality_check_required', 'quality_check_passed',
            'notes', 'damage_report', 'items',
            'total_quantity_received', 'total_quantity_damaged',
            'total_value', 'item_count', 'quality_pass_rate',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'receipt_number', 'total_quantity_received', 'total_quantity_damaged',
            'total_value', 'item_count', 'quality_pass_rate'
        ]
    
    def get_total_quantity_received(self, obj):
        """Get total quantity received."""
        return sum(item.quantity_received for item in obj.items.all())
    
    def get_total_quantity_damaged(self, obj):
        """Get total quantity damaged."""
        return sum(item.quantity_damaged for item in obj.items.all())
    
    def get_total_value(self, obj):
        """Calculate total receipt value."""
        return sum(item.quantity_received * item.unit_cost for item in obj.items.all())
    
    def get_item_count(self, obj):
        """Get number of items in receipt."""
        return obj.items.count()
    
    def get_quality_pass_rate(self, obj):
        """Calculate quality pass rate."""
        items = obj.items.all()
        if not items:
            return None
        
        passed_items = sum(1 for item in items if item.quality_check_passed)
        return (passed_items / len(items)) * 100

class StockReceiptDetailSerializer(StockReceiptSerializer):
    """Detailed stock receipt serializer."""
    
    variance_summary = serializers.SerializerMethodField()
    processing_time = serializers.SerializerMethodField()
    
    class Meta(StockReceiptSerializer.Meta):
        fields = StockReceiptSerializer.Meta.fields + [
            'variance_summary', 'processing_time'
        ]
    
    def get_variance_summary(self, obj):
        """Get variance summary for receipt."""
        items = obj.items.all()
        
        total_ordered = sum(
            item.purchase_order_item.quantity if item.purchase_order_item else 0
            for item in items
        )
        total_received = sum(item.quantity_received for item in items)
        
        return {
            'total_ordered': total_ordered,
            'total_received': total_received,
            'variance_quantity': total_received - total_ordered,
            'variance_percentage': ((total_received - total_ordered) / total_ordered * 100) if total_ordered > 0 else 0,
            'items_with_variance': sum(1 for item in items if item.quantity_received != (item.purchase_order_item.quantity if item.purchase_order_item else 0))
        }
    
    def get_processing_time(self, obj):
        """Calculate processing time."""
        if obj.created_at and obj.updated_at:
            delta = obj.updated_at - obj.created_at
            return {
                'hours': delta.total_seconds() / 3600,
                'status': 'PROCESSED' if obj.status == 'COMPLETED' else 'IN_PROGRESS'
            }
        return None

class StockReceiptCreateSerializer(NestedCreateUpdateSerializer):
    """Serializer for creating stock receipts."""
    
    items = StockReceiptItemSerializer(many=True)
    
    class Meta:
        model = StockReceipt
        fields = [
            'purchase_order', 'warehouse', 'received_date',
            'quality_check_required', 'notes', 'items'
        ]
    
    def create(self, validated_data):
        """Create stock receipt with items."""
        items_data = validated_data.pop('items')
        
        # Set tenant and received_by
        validated_data['tenant'] = self.context['request'].user.tenant
        validated_data['received_by'] = self.context['request'].user
        
        with transaction.atomic():
            # Create receipt
            receipt = StockReceipt.objects.create(**validated_data)
            
            # Create items
            for item_data indata['receipt'] = receipt
                StockReceiptItem.objects.create(**item_data)
        
        return receipt