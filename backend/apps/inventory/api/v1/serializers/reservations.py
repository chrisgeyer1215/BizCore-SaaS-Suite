# apps/inventory/api/v1/serializers/reservations.py

from rest_framework import serializers
from decimal import Decimal
from django.utils import timezone
from django.db import transaction
from apps.inventory.models.reservations import StockReservation, StockReservationItem
from .base import AuditableSerializer, DynamicFieldsSerializer, NestedCreateUpdateSerializer

class StockReservationItemSerializer(serializers.ModelSerializer):
    """Serializer for stock reservation items."""
    
    product_name = serializers.CharField(source='stock_item.product.name', read_only=True)
    product_sku = serializers.CharField(source='stock_item.product.sku', read_only=True)
    warehouse_name = serializers.CharField(source='stock_item.warehouse.name', read_only=True)
    location_name = serializers.CharField(source='stock_item.location.name', read_only=True, allow_null=True)
    
    available_quantity = serializers.SerializerMethodField()
    reservation_value = serializers.SerializerMethodField()
    unit_cost = serializers.CharField(source='stock_item.unit_cost', read_only=True)
    
    class Meta:
        model = StockReservationItem
        fields = [
            'id', 'stock_item', 'product_name', 'product_sku',
            'warehouse_name', 'location_name', 'quantity',
            'unit_cost', 'reservation_value', 'available_quantity',
            'fulfilled_quantity', 'notes'
        ]
        read_only_fields = ['reservation_value', 'available_quantity', 'fulfilled_quantity']
    
    def get_available_quantity(self, obj):
        """Get available quantity before this reservation."""
        return obj.stock_item.quantity_available + obj.quantity if obj.stock_item else 0
    
    def get_reservation_value(self, obj):
        """Calculate reservation value."""
        if obj.stock_item:
            return obj.quantity * obj.stock_item.unit_cost
        return Decimal('0')
    
    def validate_quantity(self, value):
        """Validate reservation quantity."""
        if value <= 0:
            raise serializers.ValidationError("Reservation quantity must be greater than 0")
        return value
    
    def validate(self, data):
        """Validate against available stock."""
        stock_item = data.get('stock_item')
        quantity = data.get('quantity', 0)
        
        if stock_item and quantity > stock_item.quantity_available:
            raise serializers.ValidationError(
                f"Cannot reserve {quantity} units. Only {stock_item.quantity_available} available."
            )
        
        return data

class StockReservationSerializer(AuditableSerializer, DynamicFieldsSerializer):
    """Main stock reservation serializer."""
    
    warehouse_name = serializers.CharField(source='warehouse.name', read_only=True)
    released_by_name = serializers.CharField(source='released_by.get_full_name', read_only=True, allow_null=True)
    fulfilled_by_name = serializers.CharField(source='fulfilled_by.get_full_name', read_only=True, allow_null=True)
    
    items = StockReservationItemSerializer(many=True, read_only=True)
    
    # Calculated fields
    total_items = serializers.SerializerMethodField()
    total_quantity = serializers.SerializerMethodField()
    total_value = serializers.SerializerMethodField()
    fulfillment_percentage = serializers.SerializerMethodField()
    
    # Status and timing
    days_until_expiry = serializers.SerializerMethodField()
    is_expired = serializers.SerializerMethodField()
    is_expiring_soon = serializers.SerializerMethodField()
    reservation_age_hours = serializers.SerializerMethodField()
    
    class Meta:
        model = StockReservation
        fields = [
            'id', 'reservation_number', 'warehouse', 'warehouse_name',
            'reservation_type', 'reference', 'reason', 'notes',
            'status', 'priority', 'expires_at',
            'released_at', 'released_by', 'released_by_name', 'release_reason',
            'fulfilled_at', 'fulfilled_by', 'fulfilled_by_name',
            'items', 'total_items', 'total_quantity', 'total_value',
            'fulfillment_percentage', 'days_until_expiry', 'is_expired',
            'is_expiring_soon', 'reservation_age_hours',
            'created_at', 'updated_at', 'created_by'
        ]
        read_only_fields = [
            'reservation_number', 'total_items', 'total_quantity', 'total_value',
            'fulfillment_percentage', 'days_until_expiry', 'is_expired',
            'is_expiring_soon', 'reservation_age_hours'
        ]
    
    def get_total_items(self, obj):
        """Get total number of reserved items."""
        return obj.items.count()
    
    def get_total_quantity(self, obj):
        """Get total reserved quantity."""
        return sum(item.quantity for item in obj.items.all())
    
    def get_total_value(self, obj):
        """Calculate total reservation value."""
        return sum(
            item.quantity * item.stock_item.unit_cost 
            for item in obj.items.all() 
            if item.stock_item
        )
    
    def get_fulfillment_percentage(self, obj):
        """Calculate fulfillment percentage."""
        if obj.status != 'FULFILLED':
            return 0
        
        total_reserved = self.get_total_quantity(obj)
        total_fulfilled = sum(item.fulfilled_quantity or 0 for item in obj.items.all())
        
        if total_reserved == 0:
            return 0
        
        return (total_fulfilled / total_reserved) * 100
    
    def get_days_until_expiry(self, obj):
        """Calculate days until expiration."""
        if not obj.expires_at:
            return None
        
        days = (obj.expires_at - timezone.now()).days
        return max(0, days)
    
    def get_is_expired(self, obj):
        """Check if reservation is expired."""
        if not obj.expires_at:
            return False
        return timezone.now() > obj.expires_at
    
    def get_is_expiring_soon(self, obj):
        """Check if reservation expires within 24 hours."""
        if not obj.expires_at:
            return False
        return obj.expires_at <= timezone.now() + timezone.timedelta(hours=24)
    
    def get_reservation_age_hours(self, obj):
        """Calculate hours since reservation was created."""
        return (timezone.now() - obj.created_at).total_seconds() / 3600
    
    def validate_expires_at(self, value):
        """Validate expiration date."""
        if value and value <= timezone.now():
            raise serializers.ValidationError("Expiration date must be in the future")
        return value

class StockReservationDetailSerializer(StockReservationSerializer):
    """Detailed reservation serializer with additional information."""
    
    history = serializers.SerializerMethodField()
    availability_check = serializers.SerializerMethodField()
    related_documents = serializers.SerializerMethodField()
    
    class Meta(StockReservationSerializer.Meta):
        fields = StockReservationSerializer.Meta.fields + [
            'history', 'availability_check', 'related_documents'
        ]
    
    def get_history(self, obj):
        """Get reservation history timeline."""
        history = []
        
        # Created
        history.append({
            'action': 'CREATED',
            'timestamp': obj.created_at,
            'user': obj.created_by.get_full_name() if obj.created_by else None,
            'description': f'Reservation created for {obj.reservation_type}'
        })
        
        # Released
        if obj.released_at:
            history.append({
                'action': 'RELEASED',
                'timestamp': obj.released_at,
                'user': obj.released_by.get_full_name() if obj.released_by else None,
                'description': f'Reservation released: {obj.release_reason or "No reason provided"}'
            })
        
        # Fulfilled
        if obj.fulfilled_at:
            history.append({
                'action': 'FULFILLED',
                'timestamp': obj.fulfilled_at,
                'user': obj.fulfilled_by.get_full_name() if obj.fulfilled_by else None,
                'description': 'Reservation fulfilled'
            })
        
        return history
    
    def get_availability_check(self, obj):
        """Check current availability of reserved items."""
        availability = []
        
        for item in obj.items.all():
            if item.stock_item:
                availability.append({
                    'product_name': item.stock_item.product.name,
                    'product_sku': item.stock_item.product.sku,
                    'reserved_quantity': item.quantity,
                    'current_available': item.stock_item.quantity_available,
                    'still_available': item.stock_item.quantity_available >= item.quantity
                })
        
        return availability
    
    def get_related_documents(self, obj):
        """Get related documents (sales orders, work orders, etc.)."""
        related = []
        
        # This would query related documents based on reference
        if obj.reference:
            # Check for sales orders, work orders, etc.
            pass
        
        return related

class StockReservationCreateSerializer(NestedCreateUpdateSerializer):
    """Serializer for creating stock reservations."""
    
    items = StockReservationItemSerializer(many=True)
    auto_assign = serializers.BooleanField(
        default=False,
        help_text="Automatically assign stock items based on FIFO/FEFO rules"
    )
    
    class Meta:
        model = StockReservation
        fields = [
            'warehouse', 'reservation_type', 'reference', 'reason',
            'notes', 'priority', 'expires_at', 'items', 'auto_assign'
        ]
    
    def create(self, validated_data):
        """Create stock reservation with items."""
        items_data = validated_data.pop('items')
        auto_assign = validated_data.pop('auto_assign', False)
        
        # Set tenant
        validated_data['tenant'] = self.context['request'].user.tenant
        validated_data['created_by'] = self.context['request'].user
        
        with transaction.atomic():
            # Create reservation
            reservation = StockReservation.objects.create(**validated_data)
            
            if auto_assign:
                # Auto-assign stock items using FIFO/FEFO logic
                self._auto_assign_stock_items(reservation, items_data)
            else:
                # Create items as
                    item_data['reservation'] = reservation
                    StockReservationItem.objects.create(**item_data)
            
            # Update stock item reserved quantities
            self._update_reserved_quantities(reservation)
        
        return reservation
    
    def _auto_assign_stock_items(self, reservation, items_data):
        """Auto-assign stock items using FIFO/FEFO logic."""
        from apps.inventory.models.stock.items import StockItem
        
        for
            product = item_data['product']
            required_quantity = item_data['quantity']
            
            # Find available stock items for this product, ordered by FIFO
            stock_items = StockItem.objects.filter(
                product=product,
                warehouse=reservation.warehouse,
                tenant=reservation.tenant,
                quantity_available__gt=0
            ).order_by('created_at')  # FIFO
            
            remaining_quantity = required_quantity
            
            for stock_item in stock_items:
                if remaining_quantity <= 0:
                    break
                
                available_qty = stock_item.quantity_available
                allocate_qty = min(remaining_quantity, available_qty)
                
                # Create reservation item
                StockReservationItem.objects.create(
                    reservation=reservation,
                    stock_item=stock_item,
                    quantity=allocate_qty,
                    notes=item_data.get('notes', '')
                )
                
                remaining_quantity -= allocate_qty
            
            if remaining_quantity > 0:
                raise serializers.ValidationError(
                    f"Insufficient stock for product {product.name}. "
                    f"Required: {required_quantity}, Available: {required_quantity - remaining_quantity}"
                )
    
    def _update_reserved_quantities(self, reservation):
        """Update reserved quantities on stock items."""
        for item in reservation.items.all():
            if item.stock_item:
                item.stock_item.quantity_reserved += item.quantity
                item.stock_item.save()
    
    def validate_items(self, value):
        """Validate reservation items."""
        if not value:
            raise serializers.ValidationError("Reservation must have at least one item")
        
        return value

class BulkReservationSerializer(serializers.Serializer):
    """Serializer for bulk reservation operations."""
    
    reservations = StockReservationCreateSerializer(many=True)
    
    def validate_reservations(self, value):
        """Validate bulk reservations."""
        if not value:
            raise serializers.ValidationError("Reservations list cannot be empty")
        
        if len(value) > 50:  # Reasonable limit
            raise serializers.ValidationError("Cannot process more than 50 reservations at once")
        
        return value
    
    def create(self, validated_data):
        """Create multiple reservations."""
        reservations_data = validated_data['reservations']
        created_reservations = []
        errors = []
        
        for i, reservation_data in enumerate(reservations_data):
            try:
                serializer = StockReservationCreateSerializer(
                    data=reservation_data, 
                    context=self.context
                )
                if serializer.is_valid():
                    reservation = serializer.save()
                    created_reservations.append(reservation)
                else:
                    errors.append({
                        'index': i,
                        'reference': reservation_data.get('reference', f'Reservation {i}'),
                        'errors': serializer.errors
                    })
            except Exception as e:
                errors.append({
                    'index': i,
                    'reference': reservation_data.get('reference', f'Reservation {i}'),
                    'errors': str(e)
                })
        
        return {
            'created_reservations': created_reservations,
            'errors': errors,
            'success_count': len(created_reservations),
            'error_count': len(errors)
        }