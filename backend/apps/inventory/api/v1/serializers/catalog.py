# apps/inventory/api/v1/serializers/catalog.py

from rest_framework import serializers
from decimal import Decimal
from apps.inventory.models.catalog import Product, ProductVariation, ProductAttributeValue
from apps.inventory.models.core import Category, Brand, UnitOfMeasure, Supplier
from apps.inventory.models.stock.items import StockItem
from .base import AuditableSerializer, DynamicFieldsSerializer, NestedCreateUpdateSerializer
from .core import CategorySerializer, BrandSerializer, SupplierSerializer

class ProductAttributeValueSerializer(serializers.ModelSerializer):
    """Serializer for product attribute values."""
    
    attribute_name = serializers.CharField(source='attribute.name', read_only=True)
    attribute_type = serializers.CharField(source='attribute.attribute_type', read_only=True)
    
    class Meta:
        model = ProductAttributeValue
        fields = [
            'id', 'attribute', 'attribute_name', 'attribute_type',
            'value_text', 'value_number', 'value_boolean', 'value_date'
        ]
    
    def validate(self, data):
        """Validate that appropriate value field is set based on attribute type."""
        attribute = data.get('attribute')
        if not attribute:
            return data
        
        value_fields = ['value_text', 'value_number', 'value_boolean', 'value_date']
        provided_values = [field for field in value_fields if data.get(field) is not None]
        
        if len(provided_values) != 1:
            raise serializers.ValidationError(
                "Exactly one value field must be provided based on attribute type"
            )
        
        # Validate correct value field for attribute type
        expected_field = f"value_{attribute.attribute_type.lower()}"
        if expected_field not in data or data[expected_field] is None:
            raise serializers.ValidationError(
                f"Must provide {expected_field} for {attribute.attribute_type} attribute"
            )
        
        return data

class ProductVariationSerializer(AuditableSerializer):
    """Serializer for product variations."""
    
    stock_summary = serializers.SerializerMethodField()
    total_stock = serializers.SerializerMethodField()
    average_cost = serializers.SerializerMethodField()
    
    class Meta:
        model = ProductVariation
        fields = [
            'id', 'product', 'name', 'sku', 'barcode', 'additional_cost',
            'weight', 'dimensions', 'is_active', 'sort_order',
            'stock_summary', 'total_stock', 'average_cost',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['stock_summary', 'total_stock', 'average_cost']
    
    def get_stock_summary(self, obj):
        """Get stock summary across all warehouses."""
        stock_items = obj.stock_items.select_related('warehouse')
        
        summary = {}
        for item in stock_items:
            warehouse_name = item.warehouse.name
            if warehouse_name not in summary:
                summary[warehouse_name] = {
                    'quantity_on_hand': 0,
                    'quantity_reserved': 0,
                    'quantity_available': 0
                }
            
            summary[warehouse_name]['quantity_on_hand'] += item.quantity_on_hand
            summary[warehouse_name]['quantity_reserved'] += item.quantity_reserved
            summary[warehouse_name]['quantity_available'] += item.quantity_available
        
        return summary
    
    def get_total_stock(self, obj):
        """Get total stock across all warehouses."""
        return obj.stock_items.aggregate(
            total=serializers.models.Sum('quantity_on_hand')
        )['total'] or 0
    
    def get_average_cost(self, obj):
        """Get weighted average cost."""
        stock_items = obj.stock_items.filter(quantity_on_hand__gt=0)
        if not stock_items.exists():
            return None
        
        total_value = sum(item.quantity_on_hand * item.unit_cost for item in stock_items)
        total_quantity = sum(item.quantity_on_hand for item in stock_items)
        
        return total_value / total_quantity if total_quantity > 0 else None
    
    def validate_sku(self, value):
        """Validate SKU uniqueness within tenant."""
        request = self.context.get('request')
        if not request:
            return value
        
        query = ProductVariation.objects.filter(
            sku=value,
            tenant=request.user.tenant
        )
        
        if self.instance:
            query = query.exclude(id=self.instance.id)
        
        if query.exists():
            raise serializers.ValidationError("SKU must be unique within your organization")
        
        return value

class ProductSerializer(AuditableSerializer, DynamicFieldsSerializer, NestedCreateUpdateSerializer):
    """Main product serializer with comprehensive functionality."""
    
    # Nested objects
    category = CategorySerializer(read_only=True)
    category_id = serializers.IntegerField(write_only=True, required=False)
    brand = BrandSerializer(read_only=True)
    brand_id = serializers.IntegerField(write_only=True, required=False)
    supplier = SupplierSerializer(read_only=True)
    supplier_id = serializers.IntegerField(write_only=True, required=False)
    uom_name = serializers.CharField(source='uom.name', read_only=True)
    
    # Variations
    variations = ProductVariationSerializer(many=True, read_only=True)
    variation_count = serializers.SerializerMethodField()
    
    # Attributes
    attributes = ProductAttributeValueSerializer(many=True, required=False)
    
    # Stock information
    stock_summary = serializers.SerializerMethodField()
    total_stock_value = serializers.SerializerMethodField()
    reorder_status = serializers.SerializerMethodField()
    
    # Analytics
    abc_classification = serializers.CharField(read_only=True)
    velocity_category = serializers.CharField(read_only=True)
    days_since_last_movement = serializers.IntegerField(read_only=True)
    
    # Financial
    gross_margin = serializers.SerializerMethodField()
    profit_margin_percentage = serializers.SerializerMethodField()
    
    class Meta:
        model = Product
        fields = [
            'id', 'name', 'sku', 'barcode', 'description', 
            'category', 'category_id', 'brand', 'brand_id',
            'supplier', 'supplier_id', 'uom', 'uom_name',
            'cost_price', 'selling_price', 'gross_margin', 'profit_margin_percentage',
            'weight', 'dimensions', 'reorder_level', 'max_stock_level',
            'lead_time_days', 'shelf_life_days', 'storage_requirements',
            'is_active', 'is_serialized', 'track_batches',
            'variations', 'variation_count', 'attributes',
            'stock_summary', 'total_stock_value', 'reorder_status',
            'abc_classification', 'velocity_category', 'days_since_last_movement',
            'created_at', 'updated_at', 'created_by', 'updated_by'
        ]
        read_only_fields = [
            'stock_summary', 'total_stock_value', 'reorder_status',
            'abc_classification', 'velocity_category', 'days_since_last_movement',
            'gross_margin', 'profit_margin_percentage'
        ]
    
    def get_variation_count(self, obj):
        """Get number of active variations."""
        return obj.variations.filter(is_active=True).count()
    
    def get_stock_summary(self, obj):
        """Get comprehensive stock summary."""
        stock_items = obj.stock_items.select_related('warehouse', 'location')
        
        total_on_hand = 0
        total_reserved = 0
        total_available = 0
        warehouses = {}
        
        for item in stock_items:
            total_on_hand += item.quantity_on_hand
            total_reserved += item.quantity_reserved
            total_available += item.quantity_available
            
            warehouse_name = item.warehouse.name
            if warehouse_name not in warehouses:
                warehouses[warehouse_name] = {
                    'warehouse_id': item.warehouse.id,
                    'quantity_on_hand': 0,
                    'quantity_reserved': 0,
                    'quantity_available': 0,
                    'locations': []
                }
            
            warehouse_data = warehouses[warehouse_name]
            warehouse_data['quantity_on_hand'] += item.quantity_on_hand
            warehouse_data['quantity_reserved'] += item.quantity_reserved
            warehouse_data['quantity_available'] += item.quantity_available
            
            warehouse_data['locations'].append({
                'location_id': item.location.id if item.location else None,
                'location_name': item.location.name if item.location else 'Default',
                'quantity_on_hand': item.quantity_on_hand,
                'quantity_reserved': item.quantity_reserved,
                'quantity_available': item.quantity_available
            })
        
        return {
            'total_on_hand': total_on_hand,
            'total_reserved': total_reserved,
            'total_available': total_available,
            'warehouse_count': len(warehouses),
            'warehouses': warehouses
        }
    
    def get_total_stock_value(self, obj):
        """Get total value of stock on hand."""
        stock_items = obj.stock_items.all()
        return sum(item.total_value for item in stock_items)
    
    def get_reorder_status(self, obj):
        """Determine if product needs reordering."""
        stock_summary = self.get_stock_summary(obj)
        total_available = stock_summary['total_available']
        
        if obj.reorder_level and total_available <= obj.reorder_level:
            return 'REORDER_NEEDED'
        elif obj.max_stock_level and total_available >= obj.max_stock_level:
            return 'OVERSTOCK'
        else:
            return 'NORMAL'
    
    def get_gross_margin(self, obj):
        """Calculate gross margin."""
        if obj.cost_price and obj.selling_price:
            return obj.selling_price - obj.cost_price
        return None
    
    def get_profit_margin_percentage(self, obj):
        """Calculate profit margin percentage."""
        if obj.cost_price and obj.selling_price and obj.cost_price > 0:
            margin = obj.selling_price - obj.cost_price
            return (margin / obj.selling_price * 100) if obj.selling_price > 0 else 0
        return None
    
    def validate_cost_price(self, value):
        """Validate cost price is reasonable."""
        if value < 0:
            raise serializers.ValidationError("Cost price cannot be negative")
        if value > 1000000:  # Reasonable upper limit
            raise serializers.ValidationError("Cost price seems unreasonably high")
        return value
    
    def validate_selling_price(self, value):
        """Validate selling price."""
        if value < 0:
            raise serializers.ValidationError("Selling price cannot be negative")
        return value
    
    def validate_reorder_level(self, value):
        """Validate reorder level."""
        if value < 0:
            raise serializers.ValidationError("Reorder level cannot be negative")
        return value
    
    def validate(self, data):
        """Cross-field validation."""
        data = super().validate(data)
        
        # Validate selling price vs cost price
        cost_price = data.get('cost_price', getattr(self.instance, 'cost_price', None))
        selling_price = data.get('selling_price', getattr(self.instance, 'selling_price', None))
        
        if cost_price and selling_price and selling_price < cost_price:
            # Warning, not error - sometimes items are sold at loss
            pass
        
        # Validate reorder level vs max stock level
        reorder_level = data.get('reorder_level', getattr(self.instance, 'reorder_level', None))
        max_stock_level = data.get('max_stock_level', getattr(self.instance, 'max_stock_level', None))
        
        if reorder_level and max_stock_level and reorder_level >= max_stock_level:
            raise serializers.ValidationError({
                'reorder_level': 'Reorder level must be less than maximum stock level'
            })
        
        return data
    
    def create(self, validated_data):
        """Create product with nested attributes."""
        attributes_data = validated_data.pop('attributes', [])
        
        # Create product
        product = super().create(validated_data)
        
        # Create attributes_data['product'] = product
            ProductAttributeValue.objects.create(**attr_data)
        
        return product
    
    def update(self, instance, validated_data):
        """Update product with nested attributes."""
        attributes_data = validated_data.pop('attributes', None)
        
        # Update product
        instance = super().update(instance, validated_data)
        
        # Update attributes if provided
        if attributes_data is not None:
            # Remove existing attributes
            instance.attributes.all().delete()
            
            # Create new attributes
            for attr_data
                ProductAttributeValue.objects.create(**attr_data)
        
        return instance

class ProductDetailSerializer(ProductSerializer):
    """Detailed product serializer with additional information."""
    
    # Recent activity
    recent_movements = serializers.SerializerMethodField()
    recent_adjustments = serializers.SerializerMethodField()
    recent_orders = serializers.SerializerMethodField()
    
    # Performance metrics
    sales_velocity = serializers.SerializerMethodField()
    turnover_ratio = serializers.SerializerMethodField()
    
    class Meta(ProductSerializer.Meta):
        fields = ProductSerializer.Meta.fields + [
            'recent_movements', 'recent_adjustments', 'recent_orders',
            'sales_velocity', 'turnover_ratio'
        ]
    
    def get_recent_movements(self, obj):
        """Get recent stock movements."""
        movements = obj.movements.select_related('warehouse', 'user').order_by('-created_at')[:10]
        
        return [
            {
                'id': movement.id,
                'movement_type': movement.movement_type,
                'quantity': movement.quantity,
                'warehouse': movement.warehouse.name,
                'created_at': movement.created_at,
                'user': movement.user.get_full_name() if movement.user else None,
                'reference': movement.reference
            }
            for movement in movements
        ]
    
    def get_recent_adjustments(self, obj):
        """Get recent stock adjustments."""
        # This would query adjustment items for this product
        return []  # Placeholder
    
    def get_recent_orders(self, obj):
        """Get recent purchase orders for this product."""
        # This would query PO items for this product
        return []  # Placeholder
    
    def get_sales_velocity(self, obj):
        """Calculate sales velocity (units per day)."""
        # This would calculate based on recent sales data
        return None  # Placeholder
    
    def get_turnover_ratio(self, obj):
        """Calculate inventory turnover ratio."""
        # This would calculate based on cost of goods sold vs average inventory
        return None  # Placeholder

class ProductCreateSerializer(serializers.ModelSerializer):
    """Optimized serializer for product creation."""
    
    variations = ProductVariationSerializer(many=True, required=False)
    attributes = ProductAttributeValueSerializer(many=True, required=False)
    initial_stock = serializers.ListField(
        child=serializers.DictField(),
        required=False,
        help_text="Initial stock entries for warehouses"
    )
    
    class Meta:
        model = Product
        fields = [
            'name', 'sku', 'barcode', 'description', 'category',
            'brand', 'supplier', 'uom', 'cost_price', 'selling_price',
            'weight', 'dimensions', 'reorder_level', 'max_stock_level',
            'lead_time_days', 'shelf_life_days', 'storage_requirements',
            'is_active', 'is_serialized', 'track_batches',
            'variations', 'attributes', 'initial_stock'
        ]
    
    def create(self, validated_data):
        """Create product with variations, attributes, and initial stock."""
        variations_data = validated_data.pop('variations', [])
        attributes_data = validated_data.pop('attributes', [])
        initial_stock_data = validated_data.pop('initial_stock', [])
        
        # Set tenant
        validated_data['tenant'] = self.context['request'].user.tenant
        
        # Create product
        product = Product.objects.create(**validated_data)
        
        # Create variations
            variation_data['product'] = product
            variation_data['tenant'] = product.tenant
            ProductVariation.objects.create(**variation_data)
        
        # Create attributes
        for attr_data in attributes_product'] = product
            ProductAttributeValue.objects.create(**attr_data)
        
        # Create initial stock
        for stock_ apps.inventory.models.stock.items import StockItem
            from apps.inventory.models.warehouse.warehouses import Warehouse
            
            warehouse_id = stock_data.get('warehouse_id')
            quantity = stock_data.get('quantity', 0)
            unit_cost = stock_data.get('unit_cost', product.cost_price)
            
            if warehouse_id and quantity > 0:
                warehouse = Warehouse.objects.get(id=warehouse_id, tenant=product.tenant)
                StockItem.objects.create(
                    product=product,
                    warehouse=warehouse,
                    quantity_on_hand=quantity,
                    unit_cost=unit_cost,
                    tenant=product.tenant
                )
        
        return product
    
    def validate_initial_stock(self, value):
        """Validate initial stock data."""
        if not value:
            return value
        
        for stock_data in value:
            if 'warehouse_id' not in_id is required for each stock entry")
            
            quantity = stock_data.get('quantity', 0)
            if quantity < 0:
                raise serializers.ValidationError("Stock quantity cannot be negative")
        
        return value

class BulkProductSerializer(serializers.Serializer):
    """Serializer for bulk product operations."""
    
    products = ProductCreateSerializer(many=True)
    
    def validate_products(self, value):
        """Validate bulk product data."""
        if not value:
            raise serializers.ValidationError("Products list cannot be empty")
        
        if len(value) > 1000:  # Reasonable limit
            raise serializers.ValidationError("Cannot process more than 1000 products at once")
        
        # Check for duplicate SKUs within the batch
        skus = [product.get('sku') for product in value if product.get('sku')]
        if len(skus) != len(set(skus)):
            raise serializers.ValidationError("Duplicate SKUs found in batch")
        
        return value
    
    def create(self, validated_data):
        """Create products in bulk."""
        products_data = validated_data['products']
        created_products = []
        errors = []
        
        for i, product_data in enumerate(products_data):
            try:
                serializer = ProductCreateSerializer(data=product_data, context=self.context)
                if serializer.is_valid():
                    product = serializer.save()
                    created_products.append(product)
                else:
                    errors.append({
                        'index': i,
                        'sku': product_data.get('sku', f'Item {i}'),
                        'errors': serializer.errors
                    })
            except Exception as e:
                errors.append({
                    'index': i,
                    'sku': product_data.get('sku', f'Item {i}'),
                    'errors': str(e)
                })
        
        return {
            'created_products': created_products,
            'errors': errors,
            'success_count': len(created_products),
            'error_count': len(errors)
        }

class ProductImageSerializer(serializers.ModelSerializer):
    """Serializer for product images."""
    
    class Meta:
        model = ProductImage  # This model would need to be created
        fields = ['id', 'product', 'image', 'alt_text', 'is_primary', 'sort_order']
    
    def validate_image(self, value):
        """Validate image file."""
        if value.size > 5 * 1024 * 1024:  # 5MB limit
            raise serializers.ValidationError("Image file size cannot exceed 5MB")
        
        valid_extensions = ['.jpg', '.jpeg', '.png', '.webp']
        if not any(value.name.lower().endswith(ext) for ext in valid_extensions):
            raise serializers.ValidationError("Invalid image format. Use JPG, PNG, or WebP")
        
        return value