# apps/inventory/api/v1/serializers/transfers.py

from rest_framework import serializers
from decimal import Decimal
from django.utils import timezone
from django.db import transaction
from apps.inventory.models.transfers import StockTransfer, StockTransferItem
from .base import AuditableSerializer, DynamicFieldsSerializer, NestedCreateUpdateSerializer

class StockTransferItemSerializer(serializers.ModelSerializer):
    """Serializer for stock transfer items."""
    
    product_name = serializers.CharField(source='product.name', read_only=True)
    product_sku = serializers.CharField(source='product.sku', read_only=True)
    from_location_name = serializers.CharField(source='from_location.name', read_only=True, allow_null=True)
    to_location_name = serializers.CharField(source='to_location.name', read_only=True, allow_null=True)
    available_quantity = serializers.SerializerMethodField()
    transfer_value = serializers.SerializerMethodField()
    
    class Meta:
        model = StockTransferItem
        fields = [
            'id', 'product', 'product_name', 'product_sku',
            'from_location', 'from_location_name', 'to_location', 'to_location_name',
            'quantity', 'unit_cost', 'transfer_value', 'available_quantity',
            'notes'
        ]
        read_only_fields = ['transfer_value', 'available_quantity']
    
    def get_available_quantity(self, obj):
        """Get available quantity at source location."""
        if hasattr(obj, 'stock_item') and obj.stock_item:
            return obj.stock_item.quantity_available
        return 0
    
    def get_transfer_value(self, obj):
        """Calculate transfer value."""
        return obj.quantity * obj.unit_cost
    
    def validate_quantity(self, value):
        """Validate transfer quantity."""
        if value <= 0:
            raise serializers.ValidationError("Transfer quantity must be greater than 0")
        return value

class StockTransferSerializer(AuditableSerializer, DynamicFieldsSerializer):
    """Main stock transfer serializer."""
    
    from_warehouse_name = serializers.CharField(source='from_warehouse.name', read_only=True)
    to_warehouse_name = serializers.CharField(source='to_warehouse.name', read_only=True)
    approved_by_name = serializers.CharField(source='approved_by.get_full_name', read_only=True, allow_null=True)
    received_by_name = serializers.CharField(source='received_by.get_full_name', read_only=True, allow_null=True)
    
    items = StockTransferItemSerializer(many=True, read_only=True)
    
    # Calculated fields
    total_items = serializers.SerializerMethodField()
    total_quantity = serializers.SerializerMethodField()
    total_value = serializers.SerializerMethodField()
    
    # Status and timing
    transfer_age_hours = serializers.SerializerMethodField()
    is_overdue = serializers.SerializerMethodField()
    progress_percentage = serializers.SerializerMethodField()
    
    class Meta:
        model = StockTransfer
        fields = [
            'id', 'transfer_number', 'from_warehouse', 'from_warehouse_name',
            'to_warehouse', 'to_warehouse_name', 'transfer_type',
            'status', 'priority', 'reason', 'notes',
            'requires_approval', 'approved_by', 'approved_by_name', 'approved_at',
            'shipped_at', 'expected_arrival', 'received_at',
            'received_by', 'received_by_name', 'tracking_number', 'carrier',
            'items', 'total_items', 'total_quantity', 'total_value',
            'transfer_age_hours', 'is_overdue', 'progress_percentage',
            'created_at', 'updated_at', 'created_by'
        ]
        read_only_fields = [
            'transfer_number', 'total_items', 'total_quantity', 'total_value',
            'transfer_age_hours', 'is_overdue', 'progress_percentage'
        ]
    
    def get_total_items(self, obj):
        """Get total number of items."""
        return obj.items.count()
    
    def get_total_quantity(self, obj):
        """Get total quantity being transferred."""
        return sum(item.quantity for item in obj.items.all())
    
    def get_total_value(self, obj):
        """Calculate total transfer value."""
        return sum(item.quantity * item.unit_cost for item in obj.items.all())
    
    def get_transfer_age_hours(self, obj):
        """Calculate hours since transfer was created."""
        return (timezone.now() - obj.created_at).total_seconds() / 3600
    
    def get_is_overdue(self, obj):
        """Check if transfer is overdue."""
        if not obj.expected_arrival or obj.status in ['COMPLETED', 'CANCELLED']:
            return False
        return timezone.now().date() > obj.expected_arrival
    
    def get_progress_percentage(self, obj):
        """Calculate transfer progress percentage."""
        status_progress = {
            'PENDING': 10,
            'APPROVED': 30,
            'IN_TRANSIT': 70,
            'COMPLETED': 100,
            'CANCELLED': 0,
            'REJECTED': 0
        }
        return status_progress.get(obj.status, 0)

class StockTransferDetailSerializer(StockTransferSerializer):
    """Detailed transfer serializer with additional information."""
    
    timeline = serializers.SerializerMethodField()
    shipping_details = serializers.SerializerMethodField()
    variance_report = serializers.SerializerMethodField()
    
    class Meta(StockTransferSerializer.Meta):
        fields = StockTransferSerializer.Meta.fields + [
            'timeline', 'shipping_details', 'variance_report'
        ]
    
    def get_timeline(self, obj):
        """Get transfer timeline with status history."""
        timeline = []
        
        # Created
        timeline.append({
            'status': 'CREATED',
            'timestamp': obj.created_at,
            'user': obj.created_by.get_full_name() if obj.created_by else None,
            'description': 'Transfer request created'
        })
        
        # Approved
        if obj.approved_at:
            timeline.append({
                'status': 'APPROVED',
                'timestamp': obj.approved_at,
                'user': obj.approved_by.get_full_name() if obj.approved_by else None,
                'description': 'Transfer approved'
            })
        
        # Shipped
        if obj.shipped_at:
            timeline.append({
                'status': 'SHIPPED',
                'timestamp': obj.shipped_at,
                'user': None,
                'description': f'Transfer shipped{" via " + obj.carrier if obj.carrier else ""}',
                'tracking_number': obj.tracking_number
            })
        
        # Received
        if obj.received_at:
            timeline.append({
                'status': 'RECEIVED',
                'timestamp': obj.received_at,
                'user': obj.received_by.get_full_name() if obj.received_by else None,
                'description': 'Transfer received and processed'
            })
        
        return timeline
    
    def get_shipping_details(self, obj):
        """Get shipping and carrier information."""
        return {
            'tracking_number': obj.tracking_number,
            'carrier': obj.carrier,
            'shipped_date': obj.shipped_at.date() if obj.shipped_at else None,
            'expected_arrival': obj.expected_arrival,
            'actual_arrival': obj.received_at.date() if obj.received_at else None,
            'days_in_transit': (obj.received_at - obj.shipped_at).days if obj.shipped_at and obj.received_at else None
        }
    
    def get_variance_report(self, obj):
        """Get variance report if transfer is completed."""
        if obj.status != 'COMPLETED':
            return None
        
        # This would include any variances between sent and received quantities
        return {
            'total_sent': self.get_total_quantity(obj),
            'total_received': self.get_total_quantity(obj),  # Placeholder
            'variance_items': [],  # Items with quantity differences
            'damage_report': obj.damage_report if hasattr(obj, 'damage_report') else None
        }

class StockTransferCreateSerializer(NestedCreateUpdateSerializer):
    """Serializer for creating stock transfers."""
    
    items = StockTransferItemSerializer(many=True)
    
    class Meta:
        model = StockTransfer
        fields = [
            'from_warehouse', 'to_warehouse', 'transfer_type',
            'priority', 'reason', 'notes', 'expected_arrival',
            'items'
        ]
    
    def create(self, validated_data):
        """Create stock transfer with items."""
        items_data = validated_data.pop('items')
        
        # Set tenant
        validated_data['tenant'] = self.context['request'].user.tenant
        validated_data['created_by'] = self.context['request'].user
        
        with transaction.atomic():
            # Create transfer
            transfer = StockTransfer.objects.create(**validated_data)
            
                item_data['transfer'] = transfer
                StockTransferItem.objects.create(**item_data)
        
        return transfer
    
    def validate_items(self, value):
        """Validate transfer items."""
        if not value:
            raise serializers.ValidationError("Transfer must have at least one item")
        
        return value
    
    def validate(self, data):
        """Cross-field validation."""
        from_warehouse = data.get('from_warehouse')
        to_warehouse = data.get('to_warehouse')
        
        if from_warehouse == to_warehouse:
            raise serializers.ValidationError(
                "Source and destination warehouses cannot be the same"
            )
        
        return data

class StockTransferApprovalSerializer(serializers.Serializer):
    """Serializer for transfer approval/rejection."""
    
    action = serializers.ChoiceField(choices=['approve', 'reject'])
    notes = serializers.CharField(required=False, allow_blank=True)
    reason = serializers.CharField(required=False, allow_blank=True)
    
    def validate(self, data):
        """Validate approval data."""
        if data['action'] == 'reject' and not data.get('reason'):
            raise serializers.ValidationError(
                "Reason is required when rejecting a transfer"
            )
        return data