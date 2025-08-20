# apps/inventory/api/v1/serializers/stock.py

from rest_framework import serializers
from decimal import Decimal
from django.utils import timezone
from apps.inventory.models.stock import StockItem, StockMovement, Batch, StockValuationLayer
from apps.inventory.models.adjustments import StockAdjustment, StockAdjustmentItem
from .base import AuditableSerializer, DynamicFieldsSerializer
from .catalog import ProductSerializer

class BatchSerializer(AuditableSerializer):
    """Serializer for batch/lot tracking."""
    
    product_name = serializers.CharField(source='product.name', read_only=True)
    supplier_name = serializers.CharField(source='supplier.name', read_only=True)
    remaining_quantity = serializers.SerializerMethodField()
    days_until_expiry = serializers.SerializerMethodField()
    is_expired = serializers.SerializerMethodField()
    
    class Meta:
        model = Batch
        fields = [
            'id', 'batch_number', 'product', 'product_name', 'supplier', 'supplier_name',
            'manufacturing_date', 'expiry_date', 'received_date', 'initial_quantity',
            'remaining_quantity', 'days_until_expiry', 'is_expired',
            'quality_status', 'notes', 'created_at', 'updated_at'
        ]
        read_only_fields = ['remaining_quantity', 'days_until_expiry', 'is_expired']
    
    def get_remaining_quantity(self, obj):
        """Get remaining quantity in stock."""
        return sum(
            item.quantity_on_hand 
            for item in obj.stock_items.all()
        )
    
    def get_days_until_expiry(self, obj):
        """Calculate days until expiry."""
        if not obj.expiry_date:
            return None
        
        days = (obj.expiry_date - timezone.now().date()).days
        return max(0, days)
    
    def get_is_expired(self, obj):
        """Check if batch is expired."""
        if not obj.expiry_date:
            return False
        return obj.expiry_date < timezone.now().date()
    
    def validate_batch_number(self, value):
        """Validate batch number uniqueness for product."""
        request = self.context.get('request')
        if not request:
            return value
        
        query = Batch.objects.filter(
            batch_number=value,
            tenant=request.user.tenant
        )
        
        if self.instance:
            query = query.exclude(id=self.instance.id)
        
        if = query.filter(product_id=self.initial_data['product'])
        
        if query.exists():
            raise serializers.ValidationError(
                "Batch number must be unique for this product"
            )
        
        return value
    
    def validate(self, data):
        """Cross-field validation."""
        manufacturing_date = data.get('manufacturing_date')
        expiry_date = data.get('expiry_date')
        received_date = data.get('received_date')
        
        # Validate date logic
        if manufacturing_date and expiry_date:
            if manufacturing_date >= expiry_date:
                raise serializers.ValidationError({
                    'expiry_date': 'Expiry date must be after manufacturing date'
                })
        
        if manufacturing_date and received_date:
            if received_date < manufacturing_date:
                raise serializers.ValidationError({
                    'received_date': 'Received date cannot be before manufacturing date'
                })
        
        return data

class StockMovementSerializer(AuditableSerializer):
    """Serializer for stock movements."""
    
    product_name = serializers.CharField(source='product.name', read_only=True)
    product_sku = serializers.CharField(source='product.sku', read_only=True)
    warehouse_name = serializers.CharField(source='warehouse.name', read_only=True)
    location_name = serializers.CharField(source='location.name', read_only=True, allow_null=True)
    batch_number = serializers.CharField(source='batch.batch_number', read_only=True, allow_null=True)
    user_name = serializers.CharField(source='user.get_full_name', read_only=True, allow_null=True)
    movement_value = serializers.SerializerMethodField()
    
    class Meta:
        model = StockMovement
        fields = [
            'id', 'product', 'product_name', 'product_sku',
            'warehouse', 'warehouse_name', 'location', 'location_name',
            'batch', 'batch_number', 'movement_type', 'quantity',
            'unit_cost', 'movement_value', 'reference', 'reason',
            'user', 'user_name', 'created_at'
        ]
        read_only_fields = ['movement_value', 'created_at']
    
    def get_movement_value(self, obj):
        """Calculate movement value."""
        return obj.quantity * obj.unit_cost
    
    def validate_quantity(self, value):
        """Validate movement quantity."""
        if value == 0:
            raise serializers.ValidationError("Movement quantity cannot be zero")
        return value
    
    def validate_unit_cost(self, value):
        """Validate unit cost."""
        if value < 0:
            raise serializers.ValidationError("Unit cost cannot be negative")
        return value

class StockValuationSerializer(serializers.ModelSerializer):
    """Serializer for stock valuation layers."""
    
    product_name = serializers.CharField(source='product.name', read_only=True)
    warehouse_name = serializers.CharField(source='warehouse.name', read_only=True)
    layer_value = serializers.SerializerMethodField()
    
    class Meta:
        model = StockValuationLayer
        fields = [
            'id', 'product', 'product_name', 'warehouse', 'warehouse_name',
            'quantity', 'unit_cost', 'layer_value', 'valuation_method',
            'created_at'
        ]
        read_only_fields = ['layer_value']
    
    def get_layer_value(self, obj):
        """Calculate layer total value."""
        return obj.quantity * obj.unit_cost

class StockItemSerializer(AuditableSerializer, DynamicFieldsSerializer):
    """Main serializer for stock items."""
    
    # Related object info
    product = ProductSerializer(read_only=True)
    product_id = serializers.IntegerField(write_only=True)
    warehouse_name = serializers.CharField(source='warehouse.name', read_only=True)
    location_name = serializers.CharField(source='location.name', read_only=True, allow_null=True)
    batch_number = serializers.CharField(source='batch.batch_number', read_only=True, allow_null=True)
    
    # Calculated fields
    quantity_available = serializers.SerializerMethodField()
    total_value = serializers.SerializerMethodField()
    average_cost = serializers.SerializerMethodField()
    last_movement_date = serializers.SerializerMethodField()
    
    # Status indicators
    is_low_stock = serializers.SerializerMethodField()
    is_overstock = serializers.SerializerMethodField()
    stock_status = serializers.SerializerMethodField()
    
    # Aging information
    days_since_last_receipt = serializers.SerializerMethodField()
    aging_category = serializers.SerializerMethodField()
    
    class Meta:
        model = StockItem
        fields = [
            'id', 'product', 'product_id', 'warehouse', 'warehouse_name',
            'location', 'location_name', 'batch', 'batch_number',
            'quantity_on_hand', 'quantity_reserved', 'quantity_available',
            'unit_cost', 'total_value', 'average_cost',
            'last_cost', 'last_receipt_date', 'last_movement_date',
            'is_low_stock', 'is_overstock', 'stock_status',
            'days_since_last_receipt', 'aging_category',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'quantity_available', 'total_value', 'average_cost',
            'last_movement_date', 'is_low_stock', 'is_overstock',
            'stock_status', 'days_since_last_receipt', 'aging_category'
        ]
    
    def get_quantity_available(self, obj):
        """Calculate available quantity (on_hand - reserved)."""
        return max(0, obj.quantity_on_hand - obj.quantity_reserved)
    
    def get_total_value(self, obj):
        """Calculate total value at current unit cost."""
        return obj.quantity_on_hand * obj.unit_cost
    
    def get_average_cost(self, obj):
        """Get average cost from valuation layers."""
        # This would calculate weighted average cost
        return obj.unit_cost  # Simplified
    
    def get_last_movement_date(self, obj):
        """Get date of last stock movement."""
        last_movement = obj.movements.order_by('-created_at').first()
        return last_movement.created_at if last_movement else None
    
    def get_is_low_stock(self, obj):
        """Check if stock is below reorder level."""
        if not obj.product.reorder_level:
            return False
        return obj.quantity_on_hand <= obj.product.reorder_level
    
    def get_is_overstock(self, obj):
        """Check if stock exceeds maximum level."""
        if not obj.product.max_stock_level:
            return False
        return obj.quantity_on_hand >= obj.product.max_stock_level
    
    def get_stock_status(self, obj):
        """Determine overall stock status."""
        if obj.quantity_on_hand == 0:
            return 'OUT_OF_STOCK'
        elif self.get_is_low_stock(obj):
            return 'LOW_STOCK'
        elif self.get_is_overstock(obj):
            return 'OVERSTOCK'
        else:
            return 'NORMAL'
    
    def get_days_since_last_receipt(self, obj):
        """Calculate days since last receipt."""
        if not obj.last_receipt_date:
            return None
        
        days = (timezone.now().date() - obj.last_receipt_date).days
        return max(0, days)
    
    def get_aging_category(self, obj):
        """Categorize stock by age."""
        days_since_receipt = self.get_days_since_last_receipt(obj)
        
        if days_since_receipt is None:
            return 'UNKNOWN'
        elif days_since_receipt <= 30:
            return 'FRESH'
        elif days_since_receipt <= 90:
            return 'MODERATE'
        elif days_since_receipt <= 180:
            return 'AGING'
        else:
            return 'STALE'

class StockItemDetailSerializer(StockItemSerializer):
    """Detailed stock item serializer with movement history."""
    
    recent_movements = serializers.SerializerMethodField()
    valuation_layers = serializers.SerializerMethodField()
    reservation_details = serializers.SerializerMethodField()
    
    class Meta(StockItemSerializer.Meta):
        fields = StockItemSerializer.Meta.fields + [
            'recent_movements', 'valuation_layers', 'reservation_details'
        ]
    
    def get_recent_movements(self, obj):
        """Get recent stock movements for this item."""
        movements = obj.movements.select_related('user').order_by('-created_at')[:10]
        
        return [
            {
                'id': movement.id,
                'movement_type': movement.movement_type,
                'quantity': movement.quantity,
                'unit_cost': movement.unit_cost,
                'reference': movement.reference,
                'reason': movement.reason,
                'user': movement.user.get_full_name() if movement.user else None,
                'created_at': movement.created_at
            }
            for movement in movements
        ]
    
    def get_valuation_layers(self, obj):
        """Get valuation layers for this stock item."""
        layers = obj.valuation_layers.order_by('-created_at')[:5]
        return StockValuationSerializer(layers, many=True).data
    
    def get_reservation_details(self, obj):
        """Get active reservations for this stock item."""
        reservations = obj.reservations.filter(
            status='ACTIVE',
            expires_at__gte=timezone.now()
        )
        
        return [
            {
                'id': reservation.id,
                'quantity': reservation.quantity,
                'reference': reservation.reference,
                'expires_at': reservation.expires_at,
                'created_at': reservation.created_at
            }
            for reservation in reservations
        ]

class StockAdjustmentItemSerializer(serializers.ModelSerializer):
    """Serializer for stock adjustment items."""
    
    product_name = serializers.CharField(source='product.name', read_only=True)
    product_sku = serializers.CharField(source='product.sku', read_only=True)
    current_quantity = serializers.SerializerMethodField()
    adjustment_value = serializers.SerializerMethodField()
    
    class Meta:
        model = StockAdjustmentItem
        fields = [
            'id', 'product', 'product_name', 'product_sku',
            'stock_item', 'current_quantity', 'quantity_adjusted',
            'unit_cost', 'adjustment_value', 'reason', 'notes'
        ]
        read_only_fields = ['current_quantity', 'adjustment_value']
    
    def get_current_quantity(self, obj):
        """Get current stock quantity."""
        return obj.stock_item.quantity_on_hand if obj.stock_item else 0
    
    def get_adjustment_value(self, obj):
        """Calculate adjustment value."""
        return obj.quantity_adjusted * obj.unit_cost

class StockAdjustmentSerializer(AuditableSerializer):
    """Serializer for stock adjustments."""
    
    items = StockAdjustmentItemSerializer(many=True)
    warehouse_name = serializers.CharField(source='warehouse.name', read_only=True)
    total_adjustment_value = serializers.SerializerMethodField()
    item_count = serializers.SerializerMethodField()
    approved_by_name = serializers.CharField(source='approved_by.get_full_name', read_only=True, allow_null=True)
    
    class Meta:
        model = StockAdjustment
        fields = [
            'id', 'adjustment_number', 'warehouse', 'warehouse_name',
            'adjustment_type', 'reason', 'reference', 'notes',
            'status', 'requires_approval', 'approved_by', 'approved_by_name',
            'approved_at', 'items', 'total_adjustment_value', 'item_count',
            'created_at', 'updated_at', 'created_by'
        ]
        read_only_fields = ['total_adjustment_value', 'item_count', 'adjustment_number']
    
    def get_total_adjustment_value(self, obj):
        """Calculate total adjustment value."""
        return sum(
            item.quantity_adjusted * item.unit_cost 
            for item in obj.items.all()
        )
    
    def get_item_count(self, obj):
        """Get number of adjustment items."""
        return obj.items.count()

class BulkStockUpdateSerializer(serializers.Serializer):
    """Serializer for bulk stock updates."""
    
    updates = serializers.ListField(
        child=serializers.DictField(),
        help_text="List of stock updates"
    )
    update_type = serializers.ChoiceField(
        choices=[
            ('ADJUSTMENT', 'Stock Adjustment'),
            ('COST_UPDATE', 'Cost Update'),
            ('REORDER_LEVELS', 'Reorder Level Update')
        ]
    )
    reason = serializers.CharField(required=False, default='Bulk update')
    
    def validate_updates(self, value):
        """Validate bulk update data."""
        if not value:
            raise serializers.ValidationError("Updates list cannot be empty")
        
        if len(value) > 500:  # Reasonable limit
            raise serializers.ValidationError("Cannot update more than 500 items at once")
        
        required_fields = {
            'ADJUSTMENT': ['stock_item_id', 'quantity'],
            'COST_UPDATE': ['stock_item_id', 'new_cost'],
            'REORDER_LEVELS': ['product_id', 'reorder_level']
        }
        
        update_type = self.initial_data.get('update_type')
        if update_type in required_fields:
            required = required_fields[update_type]
            for i, update in enumerate(value):
                for field in required:
                    if field not in update:
                        raise serializers.ValidationError(
                            f"Update {i}: Missing required field '{field}'"
                        )
        
        return value