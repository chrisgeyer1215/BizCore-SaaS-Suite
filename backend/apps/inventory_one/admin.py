"""
Comprehensive Django Admin interface for Inventory Management
"""

from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.db.models import Sum, Count
from django.contrib.admin import SimpleListFilter
import json

from apps.core.admin import TenantAdminMixin
from .models import (
    InventorySettings, UnitOfMeasure, Department, Category, SubCategory,
    Brand, Supplier, SupplierContact, Warehouse, StockLocation,
    ProductAttribute, AttributeValue, Product, ProductAttributeValue,
    ProductVariation, ProductSupplier, Batch, SerialNumber, StockItem,
    StockMovement, StockValuationLayer, PurchaseOrder, PurchaseOrderItem,
    StockReceipt, StockReceiptItem, StockTransfer, StockTransferItem,
    CycleCount, CycleCountItem, StockAdjustment, StockAdjustmentItem,
    StockReservation, StockReservationItem, InventoryAlert, InventoryReport,
    VendorManagedInventory, VMIProduct
)


# ============================================================================
# CUSTOM FILTERS
# ============================================================================

class StockStatusFilter(SimpleListFilter):
    """Custom filter for stock status"""
    title = 'Stock Status'
    parameter_name = 'stock_status'
    
    def lookups(self, request, model_admin):
        return (
            ('in_stock', 'In Stock'),
            ('low_stock', 'Low Stock'),
            ('out_of_stock', 'Out of Stock'),
            ('overstock', 'Overstock'),
        )
    
    def queryset(self, request, queryset):
        if self.value() == 'in_stock':
            return queryset.filter(stock_items__quantity_available__gt=0)
        elif self.value() == 'low_stock':
            return queryset.filter(
                stock_items__quantity_available__lte=models.F('reorder_point'),
                stock_items__quantity_available__gt=0
            )
        elif self.value() == 'out_of_stock':
            return queryset.filter(stock_items__quantity_available__lte=0)
        return queryset


class ABCClassificationFilter(SimpleListFilter):
    """Filter by ABC classification"""
    title = 'ABC Classification'
    parameter_name = 'abc_class'
    
    def lookups(self, request, model_admin):
        return (
            ('A', 'Class A (High Value)'),
            ('B', 'Class B (Medium Value)'),
            ('C', 'Class C (Low Value)'),
        )
    
    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(abc_classification=self.value())
        return queryset


# ============================================================================
# CORE SETTINGS & CONFIGURATION
# ============================================================================

@admin.register(InventorySettings)
class InventorySettingsAdmin(TenantAdminMixin, admin.ModelAdmin):
    fieldsets = (
        ('Core Settings', {
            'fields': ('valuation_method', 'default_currency', 'enable_multi_currency', 'decimal_precision')
        }),
        ('Stock Management', {
            'fields': ('low_stock_alert_enabled', 'low_stock_threshold_percentage', 'auto_reorder_enabled',
                      'allow_negative_stock', 'enable_reserved_stock', 'enable_allocated_stock')
        }),
        ('Advanced Tracking', {
            'fields': ('enable_batch_tracking', 'enable_serial_tracking', 'enable_lot_tracking',
                      'enable_expiry_tracking', 'enable_landed_cost'),
            'classes': ('collapse',)
        }),
        ('Barcode & Identification', {
            'fields': ('enable_barcode', 'enable_qr_code', 'auto_generate_barcodes', 'barcode_prefix'),
            'classes': ('collapse',)
        }),
        ('Manufacturing & Assembly', {
            'fields': ('enable_manufacturing', 'enable_kitting', 'enable_bundling'),
            'classes': ('collapse',)
        }),
        ('Quality Control', {
            'fields': ('enable_quality_control', 'enable_inspection', 'enable_quarantine'),
            'classes': ('collapse',)
        }),
        ('Pricing & Costing', {
            'fields': ('enable_dynamic_pricing', 'enable_tier_pricing', 'cost_calculation_method'),
            'classes': ('collapse',)
        }),
        ('Reporting & Analytics', {
            'fields': ('enable_abc_analysis', 'enable_velocity_analysis', 'enable_seasonality_tracking'),
            'classes': ('collapse',)
        }),
        ('Audit & Compliance', {
            'fields': ('require_approval_for_adjustments', 'enable_audit_trail', 'retain_data_years'),
            'classes': ('collapse',)
        }),
    )
    
    def has_add_permission(self, request):
        # Only allow one settings record per tenant
        try:
            if hasattr(request, 'tenant') and request.tenant:
                return not InventorySettings.objects.filter(tenant=request.tenant).exists()
            else:
                return True 
        except Exception as e:
            # Log the error and allow creation
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error checking InventorySettings permission: {str(e)}")
            return True
    
@admin.register(UnitOfMeasure)
class UnitOfMeasureAdmin(TenantAdminMixin, admin.ModelAdmin):
    list_display = ('name', 'abbreviation', 'symbol', 'unit_type', 'base_unit', 'is_active')
    list_filter = ('unit_type', 'is_active', 'is_base_unit')
    search_fields = ('name', 'abbreviation', 'symbol')
    ordering = ('unit_type', 'name')
    
    fieldsets = (
        (None, {
            'fields': ('name', 'abbreviation', 'symbol', 'unit_type', 'description')
        }),
        ('Conversion', {
            'fields': ('base_unit', 'conversion_factor', 'conversion_offset'),
            'classes': ('collapse',)
        }),
        ('Properties', {
            'fields': ('is_active', 'is_base_unit', 'allow_fractions', 'decimal_places')
        }),
    )


# ============================================================================
# CATEGORIZATION
# ============================================================================

@admin.register(Department)
class DepartmentAdmin(TenantAdminMixin, admin.ModelAdmin):
    list_display = ('code', 'name', 'parent', 'manager', 'is_active', 'sort_order', 'product_count')
    list_filter = ('is_active', 'parent')
    search_fields = ('name', 'code', 'description')
    ordering = ('sort_order', 'name')
    prepopulated_fields = {'code': ('name',)}
    
    fieldsets = (
        (None, {
            'fields': ('name', 'code', 'description', 'parent')
        }),
        ('Settings', {
            'fields': ('is_active', 'sort_order', 'manager')
        }),
        ('Accounting', {
            'fields': ('revenue_account_code', 'cost_account_code', 'default_markup_percentage', 'commission_percentage'),
            'classes': ('collapse',)
        }),
        ('Media', {
            'fields': ('image', 'icon_class'),
            'classes': ('collapse',)
        }),
    )
    
    def product_count(self, obj):
        return obj.products.count()
    product_count.short_description = 'Products'


@admin.register(Category)
class CategoryAdmin(TenantAdminMixin, admin.ModelAdmin):
    list_display = ('code', 'name', 'department', 'parent', 'is_active', 'sort_order', 'product_count')
    list_filter = ('department', 'parent', 'is_active')
    search_fields = ('name', 'code', 'description')
    ordering = ('department__name', 'sort_order', 'name')
    prepopulated_fields = {'code': ('name',)}
    
    def product_count(self, obj):
        return obj.products.count()
    product_count.short_description = 'Products'


@admin.register(SubCategory)
class SubCategoryAdmin(TenantAdminMixin, admin.ModelAdmin):
    list_display = ('code', 'name', 'category', 'is_active', 'sort_order', 'product_count')
    list_filter = ('category__department', 'category', 'is_active')
    search_fields = ('name', 'code', 'description')
    ordering = ('category__name', 'sort_order', 'name')
    prepopulated_fields = {'code': ('name',)}
    
    def product_count(self, obj):
        return obj.products.count()
    product_count.short_description = 'Products'


# ============================================================================
# BRANDS & SUPPLIERS
# ============================================================================

@admin.register(Brand)
class BrandAdmin(TenantAdminMixin, admin.ModelAdmin):
    list_display = ('code', 'name', 'country_of_origin', 'quality_rating', 'is_active', 'is_preferred', 'product_count')
    list_filter = ('is_active', 'is_preferred', 'manufacturer', 'country_of_origin')
    search_fields = ('name', 'code', 'description')
    ordering = ('-is_preferred', 'name')
    prepopulated_fields = {'code': ('name',)}
    
    fieldsets = (
        (None, {
            'fields': ('name', 'code', 'description')
        }),
        ('Contact Information', {
            'fields': ('website', 'email', 'phone'),
            'classes': ('collapse',)
        }),
        ('Business Details', {
            'fields': ('manufacturer', 'country_of_origin', 'established_year'),
            'classes': ('collapse',)
        }),
        ('Quality & Status', {
            'fields': ('quality_rating', 'is_active', 'is_preferred')
        }),
        ('Media', {
            'fields': ('logo', 'logo_url'),
            'classes': ('collapse',)
        }),
    )
    
    def product_count(self, obj):
        return obj.products.count()
    product_count.short_description = 'Products'


class SupplierContactInline(admin.TabularInline):
    model = SupplierContact
    extra = 1
    fields = ('contact_type', 'name', 'title', 'email', 'phone', 'is_primary', 'is_active')


@admin.register(Supplier)
class SupplierAdmin(TenantAdminMixin, admin.ModelAdmin):
    list_display = ('code', 'name', 'supplier_type', 'email', 'phone', 'overall_rating', 'is_active', 'is_preferred')
    list_filter = ('supplier_type', 'is_active', 'is_preferred', 'is_verified', 'country')
    search_fields = ('name', 'code', 'company_name', 'email', 'phone')
    ordering = ('-is_preferred', 'name')
    inlines = [SupplierContactInline]
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'code', 'company_name', 'supplier_type')
        }),
        ('Contact Information', {
            'fields': ('contact_person', 'title', 'email', 'phone', 'mobile', 'website')
        }),
        ('Address', {
            'fields': ('address_line1', 'address_line2', 'city', 'state', 'country', 'postal_code'),
            'classes': ('collapse',)
        }),
        ('Financial Terms', {
            'fields': ('payment_terms', 'payment_terms_days', 'credit_limit', 'currency'),
            'classes': ('collapse',)
        }),
        ('Performance', {
            'fields': ('quality_rating', 'delivery_rating', 'service_rating', 'overall_rating'),
            'classes': ('collapse',)
        }),
        ('Status', {
            'fields': ('is_active', 'is_preferred', 'is_verified')
        }),
    )
    
    readonly_fields = ('overall_rating',)


# ============================================================================
# WAREHOUSES & LOCATIONS
# ============================================================================

class StockLocationInline(admin.TabularInline):
    model = StockLocation
    extra = 0
    fields = ('name', 'code', 'location_type', 'zone', 'aisle', 'rack', 'shelf', 'is_active')
    ordering = ('zone', 'aisle', 'rack', 'shelf')


@admin.register(Warehouse)
class WarehouseAdmin(TenantAdminMixin, admin.ModelAdmin):
    list_display = ('code', 'name', 'warehouse_type', 'city', 'manager', 'is_active', 'is_default', 'total_stock_value')
    list_filter = ('warehouse_type', 'is_active', 'is_default', 'temperature_zone', 'country')
    search_fields = ('name', 'code', 'city', 'state')
    ordering = ('-is_default', 'name')
    inlines = [StockLocationInline]
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'code', 'warehouse_type', 'description')
        }),
        ('Address & Location', {
            'fields': ('address_line1', 'address_line2', 'city', 'state', 'country', 'postal_code'),
        }),
        ('Contact & Management', {
            'fields': ('manager', 'phone', 'email')
        }),
        ('Operational Settings', {
            'fields': ('is_active', 'is_default', 'is_sellable', 'allow_negative_stock'),
        }),
        ('Capacity & Environment', {
            'fields': ('total_area', 'storage_area', 'temperature_zone', 'min_temperature', 'max_temperature'),
            'classes': ('collapse',)
        }),
        ('Costs', {
            'fields': ('rent_cost_per_month', 'utility_cost_per_month', 'labor_cost_per_month'),
            'classes': ('collapse',)
        }),
    )
    
    def total_stock_value(self, obj):
        total = obj.stock_items.filter(is_active=True).aggregate(
            total=Sum('total_value')
        )['total'] or 0
        return f"${total:,.2f}"
    total_stock_value.short_description = 'Stock Value'


@admin.register(StockLocation)
class StockLocationAdmin(TenantAdminMixin, admin.ModelAdmin):
    list_display = ('code', 'name', 'warehouse', 'location_type', 'zone', 'aisle', 'rack', 'shelf', 'is_active')
    list_filter = ('warehouse', 'location_type', 'is_active', 'is_pickable', 'is_receivable')
    search_fields = ('name', 'code', 'zone', 'aisle', 'rack', 'shelf')
    ordering = ('warehouse__name', 'zone', 'aisle', 'rack', 'shelf')


# ============================================================================
# PRODUCT ATTRIBUTES
# ============================================================================

class AttributeValueInline(admin.TabularInline):
    model = AttributeValue
    extra = 1
    fields = ('value', 'display_name', 'color_code', 'is_active', 'is_default', 'sort_order')
    ordering = ('sort_order', 'display_name')


@admin.register(ProductAttribute)
class ProductAttributeAdmin(TenantAdminMixin, admin.ModelAdmin):
    list_display = ('name', 'display_name', 'attribute_type', 'attribute_group', 'is_required', 'is_active', 'sort_order')
    list_filter = ('attribute_type', 'is_active', 'is_required', 'is_variant_attribute', 'attribute_group')
    search_fields = ('name', 'display_name', 'attribute_group')
    ordering = ('attribute_group', 'sort_order', 'name')
    inlines = [AttributeValueInline]
    prepopulated_fields = {'slug': ('name',)}
    
    fieldsets = (
        (None, {
            'fields': ('name', 'slug', 'display_name', 'attribute_type', 'attribute_group')
        }),
        ('Validation & Properties', {
            'fields': ('is_required', 'is_unique', 'is_searchable', 'is_filterable', 'is_variant_attribute')
        }),
        ('Display', {
            'fields': ('sort_order', 'help_text', 'placeholder_text')
        }),
        ('Advanced', {
            'fields': ('validation_rules', 'default_value', 'unit'),
            'classes': ('collapse',)
        }),
    )


# ============================================================================
# PRODUCTS
# ============================================================================

class ProductVariationInline(admin.TabularInline):
    model = ProductVariation
    extra = 0
    fields = ('name', 'variation_code', 'sku', 'cost_price', 'selling_price', 'is_active', 'sort_order')
    readonly_fields = ('variation_code',)


class ProductSupplierInline(admin.TabularInline):
    model = ProductSupplier
    extra = 0
    fields = ('supplier', 'supplier_sku', 'cost_price', 'minimum_order_quantity', 'lead_time_days', 'is_preferred')


class ProductAttributeValueInline(admin.TabularInline):
    model = ProductAttributeValue
    extra = 0
    fields = ('attribute', 'text_value', 'number_value', 'date_value', 'boolean_value')


@admin.register(Product)
class ProductAdmin(TenantAdminMixin, admin.ModelAdmin):
    list_display = ('sku', 'name', 'department', 'category', 'brand', 'status', 'selling_price', 'total_stock', 'is_saleable')
    list_filter = ('status', 'product_type', 'department', 'category', 'brand', 'is_saleable', 'is_purchasable', 
                   StockStatusFilter, ABCClassificationFilter)
    search_fields = ('name', 'sku', 'barcode', 'description')
    ordering = ('name',)
    inlines = [ProductVariationInline, ProductSupplierInline, ProductAttributeValueInline]
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'sku', 'internal_code', 'model_number', 'part_number', 'description')
        }),
        ('Identification', {
            'fields': ('barcode', 'upc', 'ean', 'isbn', 'qr_code'),
            'classes': ('collapse',)
        }),
        ('Categorization', {
            'fields': ('product_type', 'department', 'category', 'subcategory', 'brand')
        }),
        ('Pricing', {
            'fields': ('cost_price', 'standard_cost', 'selling_price', 'msrp', 'map_price')
        }),
        ('Inventory Settings', {
            'fields': ('unit', 'track_inventory', 'min_stock_level', 'max_stock_level', 
                      'reorder_point', 'reorder_quantity', 'safety_stock'),
            'classes': ('collapse',)
        }),
        ('Physical Properties', {
            'fields': ('weight', 'weight_unit', 'length', 'width', 'height', 'dimension_unit'),
            'classes': ('collapse',)
        }),
        ('Advanced Tracking', {
            'fields': ('is_serialized', 'is_lot_tracked', 'is_batch_tracked', 'is_perishable', 'shelf_life_days'),
            'classes': ('collapse',)
        }),
        ('Sales & Purchase', {
            'fields': ('is_purchasable', 'is_saleable', 'is_returnable', 'is_shippable', 'is_featured')
        }),
        ('Status & Lifecycle', {
            'fields': ('status', 'lifecycle_stage', 'launch_date', 'discontinue_date')
        }),
        ('SEO & Marketing', {
            'fields': ('seo_title', 'seo_description', 'seo_keywords', 'tags'),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = ('sku',)
    
    def total_stock(self, obj):
        return obj.total_stock
    total_stock.short_description = 'Stock'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'department', 'category', 'subcategory', 'brand', 'unit'
        ).prefetch_related('stock_items')


@admin.register(Batch)
class BatchAdmin(TenantAdminMixin, admin.ModelAdmin):
    list_display = ('batch_number', 'product', 'supplier', 'manufacture_date', 'expiry_date', 
                   'current_quantity', 'status', 'quality_grade')
    list_filter = ('status', 'quality_grade', 'supplier', 'product__category')
    search_fields = ('batch_number', 'lot_number', 'product__name', 'product__sku')
    ordering = ('expiry_date', 'received_date')
    date_hierarchy = 'expiry_date'
    
    fieldsets = (
        ('Batch Information', {
            'fields': ('product', 'batch_number', 'lot_number', 'supplier')
        }),
        ('Dates', {
            'fields': ('manufacture_date', 'expiry_date', 'best_before_date', 'received_date')
        }),
        ('Quantities', {
            'fields': ('initial_quantity', 'current_quantity', 'reserved_quantity')
        }),
        ('Quality', {
            'fields': ('quality_grade', 'quality_notes', 'status')
        }),
        ('Costing', {
            'fields': ('unit_cost', 'total_cost', 'landed_cost_per_unit'),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('product', 'supplier')


# ============================================================================
# STOCK MANAGEMENT
# ============================================================================

@admin.register(StockItem)
class StockItemAdmin(TenantAdminMixin, admin.ModelAdmin):
    list_display = ('product', 'warehouse', 'location', 'quantity_on_hand', 'quantity_available', 
                   'quantity_reserved', 'average_cost', 'total_value', 'abc_classification')
    list_filter = ('warehouse', 'is_active', 'is_quarantined', 'abc_classification', 'product__category')
    search_fields = ('product__name', 'product__sku', 'warehouse__name', 'location__name')
    ordering = ('product__name', 'warehouse__name')
    readonly_fields = ('total_value', 'last_movement_date', 'turnover_rate')
    
    fieldsets = (
        ('Product & Location', {
            'fields': ('product', 'variation', 'warehouse', 'location', 'batch')
        }),
        ('Quantities', {
            'fields': ('quantity_on_hand', 'quantity_available', 'quantity_reserved', 
                      'quantity_allocated', 'quantity_incoming')
        }),
        ('Costing', {
            'fields': ('unit_cost', 'average_cost', 'standard_cost', 'last_cost', 'total_value')
        }),
        ('Classification & Performance', {
            'fields': ('abc_classification', 'xyz_classification', 'turnover_rate', 'days_on_hand'),
            'classes': ('collapse',)
        }),
        ('Cycle Counting', {
            'fields': ('last_counted_date', 'cycle_count_frequency_days', 'next_count_due'),
            'classes': ('collapse',)
        }),
        ('Status & Flags', {
            'fields': ('is_active', 'is_quarantined', 'is_consignment', 'is_dropship')
        }),
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'product', 'warehouse', 'location', 'batch'
        )


@admin.register(StockMovement)
class StockMovementAdmin(TenantAdminMixin, admin.ModelAdmin):
    list_display = ('movement_id', 'stock_item', 'movement_type', 'quantity', 'unit_cost', 
                   'movement_date', 'performed_by', 'reference_number')
    list_filter = ('movement_type', 'movement_reason', 'movement_date', 'stock_item__warehouse')
    search_fields = ('stock_item__product__name', 'stock_item__product__sku', 'reference_number', 'reason')
    ordering = ('-movement_date',)
    readonly_fields = ('movement_id', 'total_cost', 'cost_impact')
    date_hierarchy = 'movement_date'
    
    fieldsets = (
        ('Movement Details', {
            'fields': ('movement_id', 'stock_item', 'movement_type', 'movement_reason', 'quantity')
        }),
        ('Cost Information', {
            'fields': ('unit_cost', 'total_cost', 'currency', 'exchange_rate')
        }),
        ('Stock Levels', {
            'fields': ('stock_before', 'stock_after'),
            'classes': ('collapse',)
        }),
        ('References', {
            'fields': ('reference_type', 'reference_id', 'reference_number'),
            'classes': ('collapse',)
        }),
        ('Personnel & Timing', {
            'fields': ('performed_by', 'authorized_by', 'movement_date', 'actual_date')
        }),
        ('Additional Info', {
            'fields': ('reason', 'notes'),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'stock_item__product', 'stock_item__warehouse', 'performed_by', 'authorized_by'
        )


# ============================================================================
# PURCHASE ORDERS
# ============================================================================

class PurchaseOrderItemInline(admin.TabularInline):
    model = PurchaseOrderItem
    extra = 0
    fields = ('line_number', 'product', 'quantity_ordered', 'unit_cost', 'total_amount', 'status')
    readonly_fields = ('total_amount',)
    ordering = ('line_number',)


@admin.register(PurchaseOrder)
class PurchaseOrderAdmin(TenantAdminMixin, admin.ModelAdmin):
    list_display = ('po_number', 'supplier', 'order_date', 'required_date', 'status', 'total_amount', 
                   'buyer', 'received_percentage')
    list_filter = ('status', 'priority', 'po_type', 'order_date', 'supplier')
    search_fields = ('po_number', 'supplier__name', 'supplier_po_number')
    ordering = ('-order_date',)
    inlines = [PurchaseOrderItemInline]
    readonly_fields = ('po_number', 'subtotal', 'total_amount', 'received_percentage')
    date_hierarchy = 'order_date'
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('po_number', 'po_type', 'supplier', 'delivery_warehouse')
        }),
        ('Dates', {
            'fields': ('order_date', 'required_date', 'promised_date', 'delivery_date')
        }),
        ('Status & Personnel', {
            'fields': ('status', 'priority', 'buyer', 'approved_by')
        }),
        ('Financial', {
            'fields': ('currency', 'subtotal', 'tax_amount', 'discount_amount', 'shipping_cost', 'total_amount')
        }),
        ('Terms & Conditions', {
            'fields': ('payment_terms', 'terms_and_conditions', 'special_instructions'),
            'classes': ('collapse',)
        }),
    )
    
    def received_percentage(self, obj):
        return f"{obj.received_percentage}%"
    received_percentage.short_description = 'Received %'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'supplier', 'delivery_warehouse', 'buyer', 'approved_by'
        )


# ============================================================================
# ALERTS & REPORTS
# ============================================================================

@admin.register(InventoryAlert)
class InventoryAlertAdmin(TenantAdminMixin, admin.ModelAdmin):
    list_display = ('alert_id', 'alert_type', 'severity', 'title', 'product', 'warehouse', 
                   'status', 'created_at', 'assigned_to')
    list_filter = ('alert_type', 'severity', 'status', 'created_at', 'warehouse')
    search_fields = ('title', 'message', 'product__name', 'product__sku')
    ordering = ('-created_at', '-severity')
    readonly_fields = ('alert_id', 'is_active', 'is_expired')
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Alert Information', {
            'fields': ('alert_id', 'alert_type', 'severity', 'title', 'message')
        }),
        ('References', {
            'fields': ('product', 'warehouse', 'stock_item'),
            'classes': ('collapse',)
        }),
        ('Status & Assignment', {
            'fields': ('status', 'assigned_to', 'acknowledged_by', 'resolved_by')
        }),
        ('Timing', {
            'fields': ('created_at', 'acknowledged_at', 'resolved_at', 'expires_at'),
            'classes': ('collapse',)
        }),
        ('Notification', {
            'fields': ('email_sent', 'sms_sent', 'notification_count'),
            'classes': ('collapse',)
        }),
        ('Additional Info', {
            'fields': ('details', 'notes', 'tags'),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'product', 'warehouse', 'assigned_to', 'acknowledged_by', 'resolved_by'
        )


# ============================================================================
# CUSTOM ADMIN ACTIONS
# ============================================================================

def make_active(modeladmin, request, queryset):
    """Bulk action to make items active"""
    updated = queryset.update(is_active=True)
    modeladmin.message_user(request, f'{updated} items marked as active.')
make_active.short_description = "Mark selected items as active"


def make_inactive(modeladmin, request, queryset):
    """Bulk action to make items inactive"""
    updated = queryset.update(is_active=False)
    modeladmin.message_user(request, f'{updated} items marked as inactive.')
make_inactive.short_description = "Mark selected items as inactive"


def calculate_abc_classification(modeladmin, request, queryset):
    """Recalculate ABC classification for products"""
    from .services import AnalyticsService
    
    analytics = AnalyticsService(request.tenant)
    analytics.calculate_abc_analysis()
    
    modeladmin.message_user(request, 'ABC classification recalculated successfully.')
calculate_abc_classification.short_description = "Recalculate ABC classification"


# Add actions to relevant admin classes
ProductAdmin.actions = [make_active, make_inactive, calculate_abc_classification]
SupplierAdmin.actions = [make_active, make_inactive]
WarehouseAdmin.actions = [make_active, make_inactive]
BrandAdmin.actions = [make_active, make_inactive]
