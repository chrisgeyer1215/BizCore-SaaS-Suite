"""
Comprehensive DRF serializers for the Inventory Management System
"""

from rest_framework import serializers
from decimal import Decimal
from django.db.models import Sum, Q
from django.utils import timezone
from django.contrib.auth import get_user_model

from apps.core.serializers import TenantBaseSerializer
from .models import (
    InventorySettings, UnitOfMeasure, Department, Category, SubCategory,
    Brand, Supplier, SupplierContact, Warehouse, StockLocation,
    ProductAttribute, AttributeValue, Product, ProductAttributeValue,
    ProductVariation, ProductSupplier, Batch, SerialNumber, StockItem,
    StockMovement, PurchaseOrder, PurchaseOrderItem, StockReceipt,
    StockReceiptItem, StockTransfer, StockTransferItem, CycleCount,
    CycleCountItem, StockAdjustment, StockAdjustmentItem, StockReservation,
    StockReservationItem, InventoryAlert, InventoryReport
)

User = get_user_model()


# ============================================================================
# CORE SETTINGS & CONFIGURATION SERIALIZERS
# ============================================================================

class InventorySettingsSerializer(TenantBaseSerializer):
    """Inventory settings serializer"""
    
    class Meta:
        model = InventorySettings
        fields = '__all__'


class UnitOfMeasureSerializer(TenantBaseSerializer):
    """Unit of measure serializer"""
    
    base_unit_name = serializers.CharField(source='base_unit.name', read_only=True)
    conversions = serializers.SerializerMethodField()
    
    class Meta:
        model = UnitOfMeasure
        fields = '__all__'
    
    def get_conversions(self, obj):
        """Get conversion factors for related units"""
        if obj.base_unit:
            return {
                'to_base': float(obj.conversion_factor),
                'from_base': float(1 / obj.conversion_factor) if obj.conversion_factor != 0 else 0
            }
        return None


# ============================================================================
# CATEGORIZATION SERIALIZERS
# ============================================================================

class DepartmentSerializer(TenantBaseSerializer):
    """Department serializer with hierarchy support"""
    
    children = serializers.SerializerMethodField()
    product_count = serializers.SerializerMethodField()
    manager_name = serializers.CharField(source='manager.get_full_name', read_only=True)
    full_path = serializers.ReadOnlyField()
    
    class Meta:
        model = Department
        fields = '__all__'
        extra_kwargs = {
            'sort_order': {'default': 0},
            'is_active': {'default': True},
        }
    
    def get_children(self, obj):
        """Get child departments"""
        children = obj.children.filter(is_active=True).order_by('sort_order', 'name')
        return DepartmentSerializer(children, many=True, context=self.context).data
    
    def get_product_count(self, obj):
        """Get total product count including child departments"""
        return obj.products.filter(status='ACTIVE').count()


class CategorySerializer(TenantBaseSerializer):
    """Category serializer"""
    
    department_name = serializers.CharField(source='department.name', read_only=True)
    children = serializers.SerializerMethodField()
    product_count = serializers.SerializerMethodField()
    full_path = serializers.ReadOnlyField()
    
    class Meta:
        model = Category
        fields = '__all__'
    
    def get_children(self, obj):
        """Get child categories"""
        children = obj.children.filter(is_active=True).order_by('sort_order', 'name')
        return CategorySerializer(children, many=True, context=self.context).data
    
    def get_product_count(self, obj):
        """Get product count for this category"""
        return obj.products.filter(status='ACTIVE').count()


class SubCategorySerializer(TenantBaseSerializer):
    """Sub-category serializer"""
    
    category_name = serializers.CharField(source='category.name', read_only=True)
    department_name = serializers.CharField(source='category.department.name', read_only=True)
    product_count = serializers.SerializerMethodField()
    full_path = serializers.ReadOnlyField()
    
    class Meta:
        model = SubCategory
        fields = '__all__'
    
    def get_product_count(self, obj):
        """Get product count for this subcategory"""
        return obj.products.filter(status='ACTIVE').count()


# ============================================================================
# BRAND & SUPPLIER SERIALIZERS
# ============================================================================

class BrandSerializer(TenantBaseSerializer):
    """Brand serializer"""
    
    product_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Brand
        fields = '__all__'
    
    def get_product_count(self, obj):
        """Get product count for this brand"""
        return obj.products.filter(status='ACTIVE').count()


class SupplierContactSerializer(TenantBaseSerializer):
    """Supplier contact serializer"""
    
    class Meta:
        model = SupplierContact
        fields = '__all__'


class SupplierSerializer(TenantBaseSerializer):
    """Comprehensive supplier serializer"""
    
    contacts = SupplierContactSerializer(many=True, read_only=True)
    product_count = serializers.SerializerMethodField()
    total_purchase_orders = serializers.SerializerMethodField()
    credit_available = serializers.ReadOnlyField()
    credit_utilization_percentage = serializers.ReadOnlyField()
    performance_score = serializers.SerializerMethodField()
    
    class Meta:
        model = Supplier
        fields = '__all__'
        extra_kwargs = {
            'is_active': {'default': True},
            'payment_terms': {'default': 'NET_30'},
            'lead_time_days': {'default': 7},
        }
    
    def get_product_count(self, obj):
        """Get number of products supplied"""
        return obj.product_items.filter(is_active=True).count()
    
    def get_total_purchase_orders(self, obj):
        """Get total purchase orders count"""
        return obj.purchase_orders.count()
    
    def get_performance_score(self, obj):
        """Calculate overall performance score"""
        ratings = [obj.quality_rating, obj.delivery_rating, obj.service_rating]
        valid_ratings = [r for r in ratings if r > 0]
        if valid_ratings:
            return sum(valid_ratings) / len(valid_ratings)
        return 0


# ============================================================================
# WAREHOUSE & LOCATION SERIALIZERS
# ============================================================================

class StockLocationSerializer(TenantBaseSerializer):
    """Stock location serializer"""
    
    warehouse_name = serializers.CharField(source='warehouse.name', read_only=True)
    full_location_code = serializers.ReadOnlyField()
    stock_items_count = serializers.SerializerMethodField()
    
    class Meta:
        model = StockLocation
        fields = '__all__'
        extra_kwargs = {
            'is_active': {'default': True},
            'is_pickable': {'default': True},
            'is_receivable': {'default': True},
        }
    
    def get_stock_items_count(self, obj):
        """Get number of stock items in this location"""
        return obj.stock_items.filter(is_active=True, quantity_available__gt=0).count()


class WarehouseSerializer(TenantBaseSerializer):
    """Comprehensive warehouse serializer"""
    
    locations = StockLocationSerializer(many=True, read_only=True)
    manager_name = serializers.CharField(source='manager.get_full_name', read_only=True)
    total_monthly_cost = serializers.ReadOnlyField()
    total_stock_value = serializers.SerializerMethodField()
    active_locations_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Warehouse
        fields = '__all__'
        extra_kwargs = {
            'is_active': {'default': True},
            'is_sellable': {'default': True},
            'warehouse_type': {'default': 'PHYSICAL'},
            'temperature_zone': {'default': 'AMBIENT'},
        }
    
    def get_total_stock_value(self, obj):
        """Calculate total stock value in warehouse"""
        total_value = obj.stock_items.filter(
            is_active=True
        ).aggregate(
            total=Sum('total_value')
        )['total']
        return float(total_value or 0)
    
    def get_active_locations_count(self, obj):
        """Get count of active locations"""
        return obj.locations.filter(is_active=True).count()


# ============================================================================
# PRODUCT ATTRIBUTE SERIALIZERS
# ============================================================================

class AttributeValueSerializer(TenantBaseSerializer):
    """Attribute value serializer"""
    
    attribute_name = serializers.CharField(source='attribute.name', read_only=True)
    
    class Meta:
        model = AttributeValue
        fields = '__all__'


class ProductAttributeSerializer(TenantBaseSerializer):
    """Product attribute serializer"""
    
    values = AttributeValueSerializer(many=True, read_only=True)
    unit_name = serializers.CharField(source='unit.name', read_only=True)
    
    class Meta:
        model = ProductAttribute
        fields = '__all__'
        extra_kwargs = {
            'is_active': {'default': True},
            'is_searchable': {'default': True},
            'is_filterable': {'default': True},
            'sort_order': {'default': 0},
        }


# ============================================================================
# PRODUCT SERIALIZERS
# ============================================================================

class ProductAttributeValueSerializer(TenantBaseSerializer):
    """Product attribute value junction serializer"""
    
    attribute_name = serializers.CharField(source='attribute.display_name', read_only=True)
    attribute_type = serializers.CharField(source='attribute.attribute_type', read_only=True)
    value_display = serializers.SerializerMethodField()
    
    class Meta:
        model = ProductAttributeValue
        fields = '__all__'
    
    def get_value_display(self, obj):
        """Get display value based on attribute type"""
        return obj.get_display_value()


class ProductVariationSerializer(TenantBaseSerializer):
    """Product variation serializer"""
    
    product_name = serializers.CharField(source='product.name', read_only=True)
    product_sku = serializers.CharField(source='product.sku', read_only=True)
    effective_cost_price = serializers.ReadOnlyField()
    effective_selling_price = serializers.ReadOnlyField()
    effective_sku = serializers.ReadOnlyField()
    attribute_display = serializers.ReadOnlyField()
    total_stock = serializers.ReadOnlyField()
    available_stock = serializers.ReadOnlyField()
    
    class Meta:
        model = ProductVariation
        fields = '__all__'
        extra_kwargs = {
            'is_active': {'default': True},
            'sort_order': {'default': 0},
        }


class ProductSupplierSerializer(TenantBaseSerializer):
    """Product supplier relationship serializer"""
    
    product_name = serializers.CharField(source='product.name', read_only=True)
    product_sku = serializers.CharField(source='product.sku', read_only=True)
    supplier_name = serializers.CharField(source='supplier.name', read_only=True)
    supplier_code = serializers.CharField(source='supplier.code', read_only=True)
    effective_lead_time = serializers.ReadOnlyField()
    
    class Meta:
        model = ProductSupplier
        fields = '__all__'
        extra_kwargs = {
            'is_active': {'default': True},
            'minimum_order_quantity': {'default': 1},
            'order_multiple': {'default': 1},
        }


class BatchSerializer(TenantBaseSerializer):
    """Batch tracking serializer"""
    
    product_name = serializers.CharField(source='product.name', read_only=True)
    product_sku = serializers.CharField(source='product.sku', read_only=True)
    supplier_name = serializers.CharField(source='supplier.name', read_only=True)
    available_quantity = serializers.ReadOnlyField()
    is_expired = serializers.ReadOnlyField()
    days_until_expiry = serializers.ReadOnlyField()
    is_near_expiry = serializers.ReadOnlyField()
    
    class Meta:
        model = Batch
        fields = '__all__'
        extra_kwargs = {
            'status': {'default': 'ACTIVE'},
            'quality_grade': {'default': 'A'},
        }


class SerialNumberSerializer(TenantBaseSerializer):
    """Serial number tracking serializer"""
    
    product_name = serializers.CharField(source='product.name', read_only=True)
    product_sku = serializers.CharField(source='product.sku', read_only=True)
    batch_number = serializers.CharField(source='batch.batch_number', read_only=True)
    location_name = serializers.CharField(source='current_location.name', read_only=True)
    warranty_active = serializers.ReadOnlyField()
    warranty_days_remaining = serializers.ReadOnlyField()
    
    class Meta:
        model = SerialNumber
        fields = '__all__'
        extra_kwargs = {
            'status': {'default': 'AVAILABLE'},
        }


class ProductSerializer(TenantBaseSerializer):
    """Comprehensive product serializer"""
    
    # Related objects
    variations = ProductVariationSerializer(many=True, read_only=True)
    attribute_values = ProductAttributeValueSerializer(many=True, read_only=True)
    supplier_items = ProductSupplierSerializer(many=True, read_only=True)
    batches = BatchSerializer(many=True, read_only=True)
    
    # Display fields
    department_name = serializers.CharField(source='department.name', read_only=True)
    category_name = serializers.CharField(source='category.name', read_only=True)
    subcategory_name = serializers.CharField(source='subcategory.name', read_only=True)
    brand_name = serializers.CharField(source='brand.name', read_only=True)
    unit_name = serializers.CharField(source='unit.name', read_only=True)
    preferred_supplier_name = serializers.CharField(source='preferred_supplier.name', read_only=True)
    full_category_path = serializers.ReadOnlyField()
    
    # Calculated fields
    margin_percentage = serializers.ReadOnlyField()
    markup_percentage = serializers.ReadOnlyField()
    total_stock = serializers.ReadOnlyField()
    available_stock = serializers.ReadOnlyField()
    reserved_stock = serializers.ReadOnlyField()
    
    # Stock status
    stock_status = serializers.SerializerMethodField()
    reorder_status = serializers.SerializerMethodField()
    
    class Meta:
        model = Product
        fields = '__all__'
        extra_kwargs = {
            'status': {'default': 'ACTIVE'},
            'product_type': {'default': 'SIMPLE'},
            'lifecycle_stage': {'default': 'INTRODUCTION'},
            'is_purchasable': {'default': True},
            'is_saleable': {'default': True},
            'track_inventory': {'default': True},
        }
    
    def get_stock_status(self, obj):
        """Get current stock status"""
        total_stock = obj.total_stock
        if total_stock <= 0:
            return 'OUT_OF_STOCK'
        elif total_stock <= obj.reorder_point:
            return 'LOW_STOCK'
        elif total_stock >= obj.max_stock_level if obj.max_stock_level else False:
            return 'OVERSTOCK'
        return 'IN_STOCK'
    
    def get_reorder_status(self, obj):
        """Get reorder recommendation"""
        total_stock = obj.total_stock
        if total_stock <= obj.reorder_point:
            recommended_qty = max(obj.reorder_quantity, obj.min_stock_level - total_stock)
            return {
                'should_reorder': True,
                'recommended_quantity': float(recommended_qty),
                'urgency': 'HIGH' if total_stock <= 0 else 'MEDIUM'
            }
        return {'should_reorder': False}


# ============================================================================
# STOCK MANAGEMENT SERIALIZERS
# ============================================================================

class StockMovementSerializer(TenantBaseSerializer):
    """Stock movement tracking serializer"""
    
    # Related object display names
    product_name = serializers.CharField(source='stock_item.product.name', read_only=True)
    product_sku = serializers.CharField(source='stock_item.product.sku', read_only=True)
    warehouse_name = serializers.CharField(source='stock_item.warehouse.name', read_only=True)
    batch_number = serializers.CharField(source='batch.batch_number', read_only=True)
    performed_by_name = serializers.CharField(source='performed_by.get_full_name', read_only=True)
    
    # Classification properties
    is_inbound = serializers.ReadOnlyField()
    is_outbound = serializers.ReadOnlyField()
    cost_impact = serializers.ReadOnlyField()
    
    class Meta:
        model = StockMovement
        fields = '__all__'
        extra_kwargs = {
            'movement_date': {'default': timezone.now},
            'is_confirmed': {'default': True},
            'currency': {'default': 'USD'},
            'exchange_rate': {'default': 1},
        }


class StockItemSerializer(TenantBaseSerializer):
    """Comprehensive stock item serializer"""
    
    # Related object display names
    product_name = serializers.CharField(source='product.name', read_only=True)
    product_sku = serializers.CharField(source='product.sku', read_only=True)
    variation_name = serializers.CharField(source='variation.name', read_only=True)
    warehouse_name = serializers.CharField(source='warehouse.name', read_only=True)
    warehouse_code = serializers.CharField(source='warehouse.code', read_only=True)
    location_name = serializers.CharField(source='location.name', read_only=True)
    batch_number = serializers.CharField(source='batch.batch_number', read_only=True)
    
    # Recent movements
    recent_movements = serializers.SerializerMethodField()
    
    # Calculated properties
    is_low_stock = serializers.ReadOnlyField()
    is_out_of_stock = serializers.ReadOnlyField()
    stock_coverage_days = serializers.ReadOnlyField()
    
    # Status indicators
    stock_status = serializers.SerializerMethodField()
    valuation_method = serializers.SerializerMethodField()
    
    class Meta:
        model = StockItem
        fields = '__all__'
        extra_kwargs = {
            'is_active': {'default': True},
            'variance_tolerance_percentage': {'default': 5},
            'cycle_count_frequency_days': {'default': 90},
        }
    
    def get_recent_movements(self, obj):
        """Get recent stock movements"""
        recent = obj.movements.select_related(
            'performed_by'
        ).order_by('-movement_date')[:5]
        return StockMovementSerializer(recent, many=True, context=self.context).data
    
    def get_stock_status(self, obj):
        """Get stock status indicator"""
        if obj.is_quarantined:
            return 'QUARANTINED'
        elif obj.is_out_of_stock:
            return 'OUT_OF_STOCK'
        elif obj.is_low_stock:
            return 'LOW_STOCK'
        return 'IN_STOCK'
    
    def get_valuation_method(self, obj):
        """Get valuation method from settings"""
        try:
            settings = InventorySettings.objects.get(tenant=obj.tenant)
            return settings.valuation_method
        except InventorySettings.DoesNotExist:
            return 'FIFO'


# ============================================================================
# PURCHASE ORDER SERIALIZERS
# ============================================================================

class PurchaseOrderItemSerializer(TenantBaseSerializer):
    """Purchase order item serializer"""
    
    # Related object display names
    product_name = serializers.CharField(source='product.name', read_only=True)
    product_sku = serializers.CharField(source='product.sku', read_only=True)
    variation_name = serializers.CharField(source='variation.name', read_only=True)
    unit_name = serializers.CharField(source='unit.name', read_only=True)
    location_name = serializers.CharField(source='delivery_location.name', read_only=True)
    
    # Calculated properties
    pending_quantity = serializers.ReadOnlyField()
    received_percentage = serializers.ReadOnlyField()
    is_fully_received = serializers.ReadOnlyField()
    is_overdue = serializers.ReadOnlyField()
    
    class Meta:
        model = PurchaseOrderItem
        fields = '__all__'
        extra_kwargs = {
            'status': {'default': 'ORDERED'},
            'unit_conversion_factor': {'default': 1},
            'discount_percentage': {'default': 0},
        }


class PurchaseOrderSerializer(TenantBaseSerializer):
    """Comprehensive purchase order serializer"""
    
    # Line items
    items = PurchaseOrderItemSerializer(many=True, read_only=True)
    
    # Related object display names
    supplier_name = serializers.CharField(source='supplier.name', read_only=True)
    supplier_code = serializers.CharField(source='supplier.code', read_only=True)
    warehouse_name = serializers.CharField(source='delivery_warehouse.name', read_only=True)
    buyer_name = serializers.CharField(source='buyer.get_full_name', read_only=True)
    approved_by_name = serializers.CharField(source='approved_by.get_full_name', read_only=True)
    
    # Calculated properties
    total_items = serializers.ReadOnlyField()
    total_quantity_ordered = serializers.ReadOnlyField()
    total_quantity_received = serializers.ReadOnlyField()
    received_percentage = serializers.ReadOnlyField()
    is_fully_received = serializers.ReadOnlyField()
    is_overdue = serializers.ReadOnlyField()
    
    # Status indicators
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    priority_display = serializers.CharField(source='get_priority_display', read_only=True)
    
    class Meta:
        model = PurchaseOrder
        fields = '__all__'
        extra_kwargs = {
            'status': {'default': 'DRAFT'},
            'priority': {'default': 'NORMAL'},
            'po_type': {'default': 'STANDARD'},
            'currency': {'default': 'USD'},
            'exchange_rate': {'default': 1},
        }


# ============================================================================
# STOCK RECEIPT SERIALIZERS
# ============================================================================

class StockReceiptItemSerializer(TenantBaseSerializer):
    """Stock receipt item serializer"""
    
    # Related object display names
    product_name = serializers.CharField(source='product.name', read_only=True)
    product_sku = serializers.CharField(source='product.sku', read_only=True)
    variation_name = serializers.CharField(source='variation.name', read_only=True)
    unit_name = serializers.CharField(source='unit.name', read_only=True)
    location_name = serializers.CharField(source='location.name', read_only=True)
    po_item_line = serializers.CharField(source='purchase_order_item.line_number', read_only=True)
    
    class Meta:
        model = StockReceiptItem
        fields = '__all__'
        extra_kwargs = {
            'quality_status': {'default': 'PENDING'},
        }


class StockReceiptSerializer(TenantBaseSerializer):
    """Stock receipt serializer"""
    
    # Line items
    items = StockReceiptItemSerializer(many=True, read_only=True)
    
    # Related object display names
    po_number = serializers.CharField(source='purchase_order.po_number', read_only=True)
    supplier_name = serializers.CharField(source='supplier.name', read_only=True)
    warehouse_name = serializers.CharField(source='warehouse.name', read_only=True)
    received_by_name = serializers.CharField(source='received_by.get_full_name', read_only=True)
    
    class Meta:
        model = StockReceipt
        fields = '__all__'
        extra_kwargs = {
            'status': {'default': 'DRAFT'},
            'receipt_type': {'default': 'PURCHASE_ORDER'},
            'receipt_date': {'default': timezone.now},
        }


# ============================================================================
# TRANSFER SERIALIZERS
# ============================================================================

class StockTransferItemSerializer(TenantBaseSerializer):
    """Stock transfer item serializer"""
    
    # Related object display names
    product_name = serializers.CharField(source='product.name', read_only=True)
    product_sku = serializers.CharField(source='product.sku', read_only=True)
    variation_name = serializers.CharField(source='variation.name', read_only=True)
    unit_name = serializers.CharField(source='unit.name', read_only=True)
    from_location_name = serializers.CharField(source='from_location.name', read_only=True)
    to_location_name = serializers.CharField(source='to_location.name', read_only=True)
    batch_number = serializers.CharField(source='batch.batch_number', read_only=True)
    
    class Meta:
        model = StockTransferItem
        fields = '__all__'
        extra_kwargs = {
            'status': {'default': 'REQUESTED'},
        }


class StockTransferSerializer(TenantBaseSerializer):
    """Stock transfer serializer"""
    
    # Line items
    items = StockTransferItemSerializer(many=True, read_only=True)
    
    # Related object display names
    from_warehouse_name = serializers.CharField(source='from_warehouse.name', read_only=True)
    to_warehouse_name = serializers.CharField(source='to_warehouse.name', read_only=True)
    requested_by_name = serializers.CharField(source='requested_by.get_full_name', read_only=True)
    approved_by_name = serializers.CharField(source='approved_by.get_full_name', read_only=True)
    
    class Meta:
        model = StockTransfer
        fields = '__all__'
        extra_kwargs = {
            'status': {'default': 'DRAFT'},
            'transfer_type': {'default': 'STANDARD'},
            'priority': {'default': 'NORMAL'},
        }


# ============================================================================
# CYCLE COUNT SERIALIZERS
# ============================================================================

class CycleCountItemSerializer(TenantBaseSerializer):
    """Cycle count item serializer"""
    
    # Related object display names
    product_name = serializers.CharField(source='stock_item.product.name', read_only=True)
    product_sku = serializers.CharField(source='stock_item.product.sku', read_only=True)
    warehouse_name = serializers.CharField(source='stock_item.warehouse.name', read_only=True)
    location_name = serializers.CharField(source='location.name', read_only=True)
    batch_number = serializers.CharField(source='batch.batch_number', read_only=True)
    counted_by_name = serializers.CharField(source='counted_by.get_full_name', read_only=True)
    
    class Meta:
        model = CycleCountItem
        fields = '__all__'
        extra_kwargs = {
            'variance_status': {'default': 'NO_VARIANCE'},
        }


class CycleCountSerializer(TenantBaseSerializer):
    """Cycle count serializer"""
    
    # Line items
    items = CycleCountItemSerializer(many=True, read_only=True)
    
    # Related object display names
    warehouse_name = serializers.CharField(source='warehouse.name', read_only=True)
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True)
    supervised_by_name = serializers.CharField(source='supervised_by.get_full_name', read_only=True)
    
    class Meta:
        model = CycleCount
        fields = '__all__'
        extra_kwargs = {
            'status': {'default': 'SCHEDULED'},
            'count_type': {'default': 'CYCLE'},
            'variance_tolerance_percentage': {'default': 5},
        }


# ============================================================================
# ADJUSTMENT SERIALIZERS
# ============================================================================

class StockAdjustmentItemSerializer(TenantBaseSerializer):
    """Stock adjustment item serializer"""
    
    # Related object display names
    product_name = serializers.CharField(source='stock_item.product.name', read_only=True)
    product_sku = serializers.CharField(source='stock_item.product.sku', read_only=True)
    warehouse_name = serializers.CharField(source='stock_item.warehouse.name', read_only=True)
    location_name = serializers.CharField(source='location.name', read_only=True)
    batch_number = serializers.CharField(source='batch.batch_number', read_only=True)
    
    class Meta:
        model = StockAdjustmentItem
        fields = '__all__'


class StockAdjustmentSerializer(TenantBaseSerializer):
    """Stock adjustment serializer"""
    
    # Line items
    items = StockAdjustmentItemSerializer(many=True, read_only=True)
    
    # Related object display names
    warehouse_name = serializers.CharField(source='warehouse.name', read_only=True)
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True)
    approved_by_name = serializers.CharField(source='approved_by.get_full_name', read_only=True)
    
    class Meta:
        model = StockAdjustment
        fields = '__all__'
        extra_kwargs = {
            'status': {'default': 'DRAFT'},
        }


# ============================================================================
# RESERVATION SERIALIZERS
# ============================================================================

class StockReservationItemSerializer(TenantBaseSerializer):
    """Stock reservation item serializer"""
    
    # Related object display names
    product_name = serializers.CharField(source='product.name', read_only=True)
    product_sku = serializers.CharField(source='product.sku', read_only=True)
    variation_name = serializers.CharField(source='variation.name', read_only=True)
    warehouse_name = serializers.CharField(source='warehouse.name', read_only=True)
    location_name = serializers.CharField(source='location.name', read_only=True)
    batch_number = serializers.CharField(source='batch.batch_number', read_only=True)
    unit_name = serializers.CharField(source='unit.name', read_only=True)
    
    # Calculated properties
    pending_quantity = serializers.ReadOnlyField()
    
    class Meta:
        model = StockReservationItem
        fields = '__all__'
        extra_kwargs = {
            'status': {'default': 'RESERVED'},
        }


class StockReservationSerializer(TenantBaseSerializer):
    """Stock reservation serializer"""
    
    # Line items
    items = StockReservationItemSerializer(many=True, read_only=True)
    
    # Related object display names
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True)
    fulfilled_by_name = serializers.CharField(source='fulfilled_by.get_full_name', read_only=True)
    
    class Meta:
        model = StockReservation
        fields = '__all__'
        extra_kwargs = {
            'status': {'default': 'ACTIVE'},
            'priority': {'default': 'NORMAL'},
            'auto_release_on_expiry': {'default': True},
        }


# ============================================================================
# ALERTS & REPORTS SERIALIZERS
# ============================================================================

class InventoryAlertSerializer(TenantBaseSerializer):
    """Inventory alert serializer"""
    
    # Related object display names
    product_name = serializers.CharField(source='product.name', read_only=True)
    product_sku = serializers.CharField(source='product.sku', read_only=True)
    warehouse_name = serializers.CharField(source='warehouse.name', read_only=True)
    acknowledged_by_name = serializers.CharField(source='acknowledged_by.get_full_name', read_only=True)
    resolved_by_name = serializers.CharField(source='resolved_by.get_full_name', read_only=True)
    assigned_to_name = serializers.CharField(source='assigned_to.get_full_name', read_only=True)
    
    # Status properties
    is_active = serializers.ReadOnlyField()
    is_expired = serializers.ReadOnlyField()
    
    class Meta:
        model = InventoryAlert
        fields = '__all__'
        extra_kwargs = {
            'status': {'default': 'ACTIVE'},
            'severity': {'default': 'MEDIUM'},
        }


class InventoryReportSerializer(TenantBaseSerializer):
    """Inventory report serializer"""
    
    # Related object display names
    generated_by_name = serializers.CharField(source='generated_by.get_full_name', read_only=True)
    
    class Meta:
        model = InventoryReport
        fields = '__all__'
        extra_kwargs = {
            'status': {'default': 'GENERATING'},
        }


# ============================================================================
# SUMMARY & DASHBOARD SERIALIZERS
# ============================================================================

class InventoryDashboardSerializer(serializers.Serializer):
    """Dashboard summary serializer"""
    
    total_products = serializers.IntegerField()
    active_products = serializers.IntegerField()
    total_stock_value = serializers.DecimalField(max_digits=15, decimal_places=2)
    low_stock_items = serializers.IntegerField()
    out_of_stock_items = serializers.IntegerField()
    expiring_batches = serializers.IntegerField()
    pending_purchase_orders = serializers.IntegerField()
    pending_receipts = serializers.IntegerField()
    active_alerts = serializers.IntegerField()
    
    # Charts data
    stock_movement_trend = serializers.ListField()
    top_selling_products = serializers.ListField()
    supplier_performance = serializers.ListField()
    warehouse_utilization = serializers.ListField()


class StockSummarySerializer(serializers.Serializer):
    """Stock summary by product serializer"""
    
    product_id = serializers.IntegerField()
    product_name = serializers.CharField()
    product_sku = serializers.CharField()
    total_stock = serializers.DecimalField(max_digits=12, decimal_places=3)
    available_stock = serializers.DecimalField(max_digits=12, decimal_places=3)
    reserved_stock = serializers.DecimalField(max_digits=12, decimal_places=3)
    allocated_stock = serializers.DecimalField(max_digits=12, decimal_places=3)
    total_value = serializers.DecimalField(max_digits=15, decimal_places=2)
    average_cost = serializers.DecimalField(max_digits=12, decimal_places=2)
    reorder_needed = serializers.BooleanField()
    stock_status = serializers.CharField()
