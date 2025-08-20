# apps/inventory/api/v1/serializers/adjustments.py

from rest_framework import serializers
from decimal import Decimal
from django.utils import timezone
from django.db import transaction
from apps.inventory.models.adjustments import StockAdjustment, StockAdjustmentItem, CycleCount, CycleCountItem
from .base import AuditableSerializer, DynamicFieldsSerializer, NestedCreateUpdateSerializer

class StockAdjustmentItemSerializer(serializers.ModelSerializer):
    """Serializer for stock adjustment items."""
    
    product_name = serializers.CharField(source='product.name', read_only=True)
    product_sku = serializers.CharField(source='product.sku', read_only=True)
    warehouse_name = serializers.CharField(source='stock_item.warehouse.name', read_only=True)
    location_name = serializers.CharField(source='stock_item.location.name', read_only=True, allow_null=True)
    
    current_quantity = serializers.SerializerMethodField()
    new_quantity = serializers.SerializerMethodField()
    adjustment_value = serializers.SerializerMethodField()
    variance_percentage = serializers.SerializerMethodField()
    
    class Meta:
        model = StockAdjustmentItem
        fields = [
            'id', 'product', 'product_name', 'product_sku',
            'stock_item', 'warehouse_name', 'location_name',
            'current_quantity', 'quantity_adjusted', 'new_quantity',
            'unit_cost', 'adjustment_value', 'variance_percentage',
            'reason', 'notes', 'batch', 'expiry_date'
        ]
        read_only_fields = [
            'current_quantity', 'new_quantity', 'adjustment_value', 'variance_percentage'
        ]
    
    def get_current_quantity(self, obj):
        """Get current stock quantity before adjustment."""
        return obj.stock_item.quantity_on_hand if obj.stock_item else 0
    
    def get_new_quantity(self, obj):
        """Calculate new quantity after adjustment."""
        current = self.get_current_quantity(obj)
        return max(0, current + obj.quantity_adjusted)
    
    def get_adjustment_value(self, obj):
        """Calculate financial impact of adjustment."""
        return obj.quantity_adjusted * obj.unit_cost
    
    def get_variance_percentage(self, obj):
        """Calculate variance percentage."""
        current = self.get_current_quantity(obj)
        if current == 0:
            return None
        return (obj.quantity_adjusted / current) * 100
    
    def validate_quantity_adjusted(self, value):
        """Validate adjustment quantity."""
        if value == 0:
            raise serializers.ValidationError("Adjustment quantity cannot be zero")
        return value
    
    def validate_unit_cost(self, value):
        """Validate unit cost."""
        if value < 0:
            raise serializers.ValidationError("Unit cost cannot be negative")
        return value
    
    def validate(self, data):
        """Cross-field validation."""
        stock_item = data.get('stock_item')
        quantity_adjusted = data.get('quantity_adjusted', 0)
        
        if stock_item and quantity_adjusted < 0:
            # For negative adjustments, ensure we don't go below zero
            new_quantity = stock_item.quantity_on_hand + quantity_adjusted
            if new_quantity < 0:
                raise serializers.ValidationError(
                    f"Adjustment would result in negative stock. "
                    f"Current: {stock_item.quantity_on_hand}, "
                    f"Adjustment: {quantity_adjusted}, "
                    f"Result: {new_quantity}"
                )
        
        return data

class StockAdjustmentSerializer(AuditableSerializer, DynamicFieldsSerializer):
    """Main stock adjustment serializer."""
    
    warehouse_name = serializers.CharField(source='warehouse.name', read_only=True)
    approved_by_name = serializers.CharField(source='approved_by.get_full_name', read_only=True, allow_null=True)
    
    items = StockAdjustmentItemSerializer(many=True, read_only=True)
    
    # Calculated fields
    total_items = serializers.SerializerMethodField()
    total_adjustment_value = serializers.SerializerMethodField()
    positive_adjustments = serializers.SerializerMethodField()
    negative_adjustments = serializers.SerializerMethodField()
    
    # Status and approval
    approval_status = serializers.SerializerMethodField()
    days_pending = serializers.SerializerMethodField()
    
    class Meta:
        model = StockAdjustment
        fields = [
            'id', 'adjustment_number', 'warehouse', 'warehouse_name',
            'adjustment_type', 'reason', 'reference', 'notes',
            'status', 'requires_approval', 'approved_by', 'approved_by_name',
            'approved_at', 'rejection_reason',
            'items', 'total_items', 'total_adjustment_value',
            'positive_adjustments', 'negative_adjustments',
            'approval_status', 'days_pending',
            'created_at', 'updated_at', 'created_by'
        ]
        read_only_fields = [
            'adjustment_number', 'total_items', 'total_adjustment_value',
            'positive_adjustments', 'negative_adjustments', 'approval_status', 'days_pending'
        ]
    
    def get_total_items(self, obj):
        """Get total number of adjustment items."""
        return obj.items.count()
    
    def get_total_adjustment_value(self, obj):
        """Calculate total financial impact."""
        return sum(item.quantity_adjusted * item.unit_cost for item in obj.items.all())
    
    def get_positive_adjustments(self, obj):
        """Calculate value of positive adjustments."""
        return sum(
            item.quantity_adjusted * item.unit_cost 
            for item in obj.items.all() 
            if item.quantity_adjusted > 0
        )
    
    def get_negative_adjustments(self, obj):
        """Calculate value of negative adjustments."""
        return abs(sum(
            item.quantity_adjusted * item.unit_cost 
            for item in obj.items.all() 
            if item.quantity_adjusted < 0
        ))
    
    def get_approval_status(self, obj):
        """Get current approval status."""
        if not obj.requires_approval:
            return 'NOT_REQUIRED'
        elif obj.status == 'APPROVED':
            return 'APPROVED'
        elif obj.status == 'REJECTED':
            return 'REJECTED'
        else:
            return 'PENDING'
    
    def get_days_pending(self, obj):
        """Calculate days since adjustment was created (if pending)."""
        if obj.status == 'PENDING':
            return (timezone.now().date() - obj.created_at.date()).days
        return None

class StockAdjustmentDetailSerializer(StockAdjustmentSerializer):
    """Detailed adjustment serializer with additional information."""
    
    approval_history = serializers.SerializerMethodField()
    impact_analysis = serializers.SerializerMethodField()
    related_documents = serializers.SerializerMethodField()
    
    class Meta(StockAdjustmentSerializer.Meta):
        fields = StockAdjustmentSerializer.Meta.fields + [
            'approval_history', 'impact_analysis', 'related_documents'
        ]
    
    def get_approval_history(self, obj):
        """Get approval workflow history."""
        history = []
        
        if obj.approved_at:
            history.append({
                'action': 'APPROVED' if obj.status == 'APPROVED' else 'REJECTED',
                'user': obj.approved_by.get_full_name() if obj.approved_by else None,
                'timestamp': obj.approved_at,
                'notes': obj.rejection_reason if obj.status == 'REJECTED' else 'Adjustment approved'
            })
        
        return history
    
    def get_impact_analysis(self, obj):
        """Analyze the impact of the adjustment."""
        items = obj.items.all()
        
        impact = {
            'categories_affected': set(),
            'high_value_items': [],
            'inventory_increase': Decimal('0'),
            'inventory_decrease': Decimal('0'),
            'net_impact': Decimal('0')
        }
        
        for item in items:
            # Track categories affected
            if item.product.category:
                impact['categories_affected'].add(item.product.category.name)
            
            # Calculate value impacts
            item_value = item.quantity_adjusted * item.unit_cost
            if item_value > 0:
                impact['inventory_increase'] += item_value
            else:
                impact['inventory_decrease'] += abs(item_value)
            
            # Track high-value items (arbitrary threshold)
            if abs(item_value) > 1000:
                impact['high_value_items'].append({
                    'product': item.product.name,
                    'sku': item.product.sku,
                    'value': item_value
                })
        
        impact['categories_affected'] = list(impact['categories_affected'])
        impact['net_impact'] = impact['inventory_increase'] - impact['inventory_decrease']
        
        return impact
    
    def get_related_documents(self, obj):
        """Get related documents (cycle counts, etc.)."""
        related = []
        
        # Check if adjustment was generated from cycle count
        if hasattr(obj, 'source_cycle_count'):
            related.append({
                'type': 'CYCLE_COUNT',
                'id': obj.source_cycle_count.id,
                'name': obj.source_cycle_count.count_name,
                'date': obj.source_cycle_count.created_at
            })
        
        return related

class StockAdjustmentCreateSerializer(NestedCreateUpdateSerializer):
    """Serializer for creating stock adjustments."""
    
    items = StockAdjustmentItemSerializer(many=True)
    
    class Meta:
        model = StockAdjustment
        fields = [
            'warehouse', 'adjustment_type', 'reason', 'reference',
            'notes', 'items'
        ]
    
    def create(self, validated_data):
        """Create stock adjustment with items."""
        items_data = validated_data.pop('items')
        
        # Set tenant and determine approval requirement
        validated_data['tenant'] = self.context['request'].user.tenant
        validated_data['created_by'] = self.context['request'].user
        
        # Calculate total value to determine if approval is required
        total_value = sum(
            abs(item['quantity_adjusted'] * item['unit_cost']) 
            for item in items_data
        )
        
        # Set approval requirement based on value threshold
        approval_threshold = Decimal('1000')  # This could come from settings
        validated_data['requires_approval'] = total_value > approval_threshold
        
        with transaction.atomic():
            # Create adjustment
            adjustment = StockAdjustment.objects.create(**validated_data)
            
            # Create items
            for item_
                StockAdjustmentItem.objects.create(**item_data)
        
        return adjustment
    
    def validate_items(self, value):
        """Validate adjustment items."""
        if not value:
            raise serializers.ValidationError("Adjustment must have at least one item")
        
        if len(value) > 100:  # Reasonable limit
            raise serializers.ValidationError("Cannot adjust more than 100 items at once")
        
        return value

class AdjustmentApprovalSerializer(serializers.Serializer):
    """Serializer for adjustment approval/rejection."""
    
    action = serializers.ChoiceField(choices=['approve', 'reject'])
    notes = serializers.CharField(required=False, allow_blank=True)
    reason = serializers.CharField(required=False, allow_blank=True)
    
    def validate(self, data):
        """Validate approval data."""
        if data['action'] == 'reject' and not data.get('reason'):
            raise serializers.ValidationError(
                "Reason is required when rejecting an adjustment"
            )
        return data

class CycleCountItemSerializer(serializers.ModelSerializer):
    """Serializer for cycle count items."""
    
    product_name = serializers.CharField(source='product.name', read_only=True)
    product_sku = serializers.CharField(source='product.sku', read_only=True)
    location_name = serializers.CharField(source='stock_item.location.name', read_only=True, allow_null=True)
    
    variance_quantity = serializers.SerializerMethodField()
    variance_value = serializers.SerializerMethodField()
    variance_percentage = serializers.SerializerMethodField()
    count_status = serializers.SerializerMethodField()
    
    class Meta:
        model = CycleCountItem
        fields = [
            'id', 'product', 'product_name', 'product_sku',
            'stock_item', 'location_name', 'expected_quantity',
            'counted_quantity', 'variance_quantity', 'unit_cost',
            'variance_value', 'variance_percentage', 'count_status',
            'notes', 'counted_by', 'counted_at'
        ]
        read_only_fields = [
            'expected_quantity', 'variance_quantity', 'variance_value',
            'variance_percentage', 'count_status'
        ]
    
    def get_variance_quantity(self, obj):
        """Calculate quantity variance."""
        if obj.counted_quantity is None:
            return None
        return obj.counted_quantity - obj.expected_quantity
    
    def get_variance_value(self, obj):
        """Calculate variance value."""
        variance_qty = self.get_variance_quantity(obj)
        if variance_qty is None:
            return None
        return variance_qty * obj.unit_cost
    
    def get_variance_percentage(self, obj):
        """Calculate variance percentage."""
        variance_qty = self.get_variance_quantity(obj)
        if variance_qty is None or obj.expected_quantity == 0:
            return None
        return (variance_qty / obj.expected_quantity) * 100
    
    def get_count_status(self, obj):
        """Determine count status."""
        if obj.counted_quantity is None:
            return 'NOT_COUNTED'
        
        variance_qty = self.get_variance_quantity(obj)
        if variance_qty == 0:
            return 'ACCURATE'
        elif abs(variance_qty) <= 1:  # Tolerance of 1 unit
            return 'WITHIN_TOLERANCE'
        else:
            return 'VARIANCE_DETECTED'

class CycleCountSerializer(AuditableSerializer, DynamicFieldsSerializer):
    """Main cycle count serializer."""
    
    warehouse_name = serializers.CharField(source='warehouse.name', read_only=True)
    items = CycleCountItemSerializer(many=True, read_only=True)
    
    # Progress tracking
    total_items = serializers.SerializerMethodField()
    counted_items = serializers.SerializerMethodField()
    progress_percentage = serializers.SerializerMethodField()
    
    # Variance summary
    items_with_variance = serializers.SerializerMethodField()
    total_variance_value = serializers.SerializerMethodField()
    accuracy_rate = serializers.SerializerMethodField()
    
    # Timing
    days_since_started = serializers.SerializerMethodField()
    estimated_completion = serializers.SerializerMethodField()
    
    class Meta:
        model = CycleCount
        fields = [
            'id', 'count_number', 'count_name', 'warehouse', 'warehouse_name',
            'count_type', 'frequency', 'status', 'priority',
            'scheduled_date', 'started_at', 'completed_at',
            'notes', 'items', 'total_items', 'counted_items',
            'progress_percentage', 'items_with_variance',
            'total_variance_value', 'accuracy_rate',
            'days_since_started', 'estimated_completion',
            'created_at', 'updated_at', 'created_by'
        ]
        read_only_fields = [
            'count_number', 'total_items', 'counted_items', 'progress_percentage',
            'items_with_variance', 'total_variance_value', 'accuracy_rate',
            'days_since_started', 'estimated_completion'
        ]
    
    def get_total_items(self, obj):
        """Get total number of items to count."""
        return obj.items.count()
    
    def get_counted_items(self, obj):
        """Get number of items already counted."""
        return obj.items.filter(counted_quantity__isnull=False).count()
    
    def get_progress_percentage(self, obj):
        """Calculate counting progress percentage."""
        total = self.get_total_items(obj)
        counted = self.get_counted_items(obj)
        
        if total == 0:
            return 0
        return (counted / total) * 100
    
    def get_items_with_variance(self, obj):
        """Get number of items with variance."""
        return obj.items.filter(
            counted_quantity__isnull=False
        ).exclude(
            counted_quantity=serializers.F('expected_quantity')
        ).count()
    
    def get_total_variance_value(self, obj):
        """Calculate total variance value."""
        total = Decimal('0')
        for item in obj.items.filter(counted_quantity__isnull=False):
            variance = item.counted_quantity - item.expected_quantity
            total += variance * item.unit_cost
        return total
    
    def get_accuracy_rate(self, obj):
        """Calculate counting accuracy rate."""
        counted = self.get_counted_items(obj)
        accurate = obj.items.filter(
            counted_quantity=serializers.F('expected_quantity')
        ).count()
        
        if counted == 0:
            return None
        return (accurate / counted) * 100
    
    def get_days_since_started(self, obj):
        """Calculate days since count started."""
        if not obj.started_at:
            return None
        return (timezone.now().date() - obj.started_at.date()).days
    
    def get_estimated_completion(self, obj):
        """Estimate completion date based on progress."""
        if obj.status == 'COMPLETED' or not obj.started_at:
            return None
        
        progress = self.get_progress_percentage(obj)
        if progress <= 0:
            return None
        
        days_elapsed = self.get_days_since_started(obj)
        estimated_total_days = days_elapsed * (100 / progress)
        remaining_days = max(0, estimated_total_days - days_elapsed)
        
        estimated_date = timezone.now().date() + timezone.timedelta(days=remaining_days)
        return estimated_date

class CycleCountDetailSerializer(CycleCountSerializer):
    """Detailed cycle count serializer."""
    
    variance_analysis = serializers.SerializerMethodField()
    count_statistics = serializers.SerializerMethodField()
    generated_adjustments = serializers.SerializerMethodField()
    
    class Meta(CycleCountSerializer.Meta):
        fields = CycleCountSerializer.Meta.fields + [
            'variance_analysis', 'count_statistics', 'generated_adjustments'
        ]
    
    def get_variance_analysis(self, obj):
        """Detailed variance analysis."""
        items = obj.items.filter(counted_quantity__isnull=False)
        
        analysis = {
            'variance_categories': {
                'positive_variance': {'count': 0, 'value': Decimal('0')},
                'negative_variance': {'count': 0, 'value': Decimal('0')},
                'no_variance': {'count': 0}
            },
            'high_value_variances': [],
            'product_categories_affected': set()
        }
        
        for item in items:
            variance_qty = item.counted_quantity - item.expected_quantity
            variance_value = variance_qty * item.unit_cost
            
            if variance_qty > 0:
                analysis['variance_categories']['positive_variance']['count'] += 1
                analysis['variance_categories']['positive_variance']['value'] += variance_value
            elif variance_qty < 0:
                analysis['variance_categories']['negative_variance']['count'] += 1
                analysis['variance_categories']['negative_variance']['value'] += abs(variance_value)
            else:
                analysis['variance_categories']['no_variance']['count'] += 1
            
            # Track high-value variances
            if abs(variance_value) > 500:  # Arbitrary threshold
                analysis['high_value_variances'].append({
                    'product': item.product.name,
                    'sku': item.product.sku,
                    'variance_quantity': variance_qty,
                    'variance_value': variance_value
                })
            
            # Track affected categories
            if item.product.category:
                analysis['product_categories_affected'].add(item.product.category.name)
        
        analysis['product_categories_affected'] = list(analysis['product_categories_affected'])
        return analysis
    
    def get_count_statistics(self, obj):
        """Get counting statistics."""
        items = obj.items.all()
        
        return {
            'average_count_time': None,  # This would require tracking count times
            'items_requiring_recount': 0,  # Items with significant variances
            'counter_performance': {},  # Performance by counter
            'location_accuracy': {}  # Accuracy by location
        }
    
    def get_generated_adjustments(self, obj):
        """Get adjustments generated from this cycle count."""
        # This would query adjustments that reference this cycle count
        return []  # Placeholder

class CycleCountCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating cycle counts."""
    
    include_products = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
        help_text="Specific product IDs to include in count"
    )
    include_categories = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
        help_text="Category IDs to include in count"
    )
    abc_classifications = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        help_text="ABC classifications to include (A, B, C)"
    )
    
    class Meta:
        model = CycleCount
        fields = [
            'count_name', 'warehouse', 'count_type', 'frequency',
            'priority', 'scheduled_date', 'notes',
            'include_products', 'include_categories', 'abc_classifications'
        ]
    
    def create(self, validated_data):
        """Create cycle count with items based on criteria."""
        include_products = validated_data.pop('include_products', [])
        include_categories = validated_data.pop('include_categories', [])
        abc_classifications = validated_data.pop('abc_classifications', [])
        
        # Set tenant
        validated_data['tenant'] = self.context['request'].user.tenant
        validated_data['created_by'] = self.context['request'].user
        
        with transaction.atomic():
            # Create cycle count
            cycle_count = CycleCount.objects.create(**validated_data)
            
            # Generate count items based on criteria
            self._generate_count_items(
                cycle_count, include_products, include_categories, abc_classifications
            )
        
        return cycle_count
    
    def _generate_count_items(self, cycle_count, product_ids, category_ids, abc_classes):
        """Generate count items based on selection criteria."""
        from apps.inventory.models.stock.items import StockItem
        
        # Build query for stock items to include
        query = StockItem.objects.filter(
            warehouse=cycle_count.warehouse,
            tenant=cycle_count.tenant
        )
        
        # Apply filters
        if product_ids:
            query = query.filter(product_id__in=product_ids)
        
        if category_ids:
            query = query.filter(product__category_id__in=category_ids)
        
        if abc_classes:
            query = query.filter(product__abc_classification__in=abc_classes)
        
        # Create count items
        for stock_item in query.select_related('product'):
            CycleCountItem.objects.create(
                cycle_count=cycle_count,
                product=stock_item.product,
                stock_item=stock_item,
                expected_quantity=stock_item.quantity_on_hand,
                unit_cost=stock_item.unit_cost
            )