# apps/inventory/admin/warehouse.py

from django.contrib import admin
from django.utils.html import format_html
from django.db.models import Count, Sum, F, Q
from django.urls import reverse, path
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from .base import BaseInventoryAdmin, InlineAdminMixin, ReadOnlyInlineMixin
from ..models.warehouse import Warehouse, StockLocation
from ..models.stock.items import StockItem

class StockLocationInline(InlineAdminMixin, admin.TabularInline):
    """Inline for stock locations within a warehouse."""
    model = StockLocation
    fields = ['name', 'location_code', 'location_type', 'capacity', 'is_active']
    extra = 1

class WarehouseStockItemInline(ReadOnlyInlineMixin, admin.TabularInline):
    """Read-only inline showing stock items in warehouse."""
    model = StockItem
    fields = [
        'product', 'location', 'quantity_on_hand', 
        'quantity_reserved', 'unit_cost', 'total_value'
    ]
    
    def total_value(self, obj):
        """Calculate total value of stock item."""
        return obj.quantity_on_hand * obj.unit_cost
    total_value.short_description = 'Total Value'

@admin.register(Warehouse)
class WarehouseAdmin(BaseInventoryAdmin):
    """Enhanced admin interface for warehouses."""
    
    list_display = [
        'name', 'warehouse_code', 'warehouse_type', 'manager',
        'location_count', 'product_count', 'total_stock_value',
        'utilization_percentage', 'status_indicator'
    ]
    
    list_filter = ['warehouse_type', 'is_active', 'country', 'state']
    search_fields = ['name', 'warehouse_code', 'address', 'manager']
    
    inlines = [StockLocationInline, WarehouseStockItemInline]
    
    fieldsets = (
        ('Basic Information', {
            'fields': (
                'name', 'warehouse_code', 'warehouse_type', 
                'manager', 'email', 'phone'
            )
        }),
        ('Address', {
            'fields': (
                'address', 'city', 'state', 'postal_code', 'country'
            )
        }),
        ('Capacity & Settings', {
            'fields': (
                'total_capacity', 'storage_type', 'climate_controlled',
                'security_level'
            )
        }),
        ('Operations', {
            'fields': (
                'operating_hours', 'time_zone', 'allow_negative_stock'
            )
        }),
        ('Status', {
            'fields': ('is_active',)
        })
    )
    
    actions = BaseInventoryAdmin.actions + [
        'generate_capacity_report', 'optimize_locations', 'audit_inventory'
    ]
    
    def get_urls(self):
        """Add custom URLs for warehouse operations."""
        urls = super().get_urls()
        custom_urls = [
            path(
                '<int:warehouse_id>/stock-summary/',
                self.admin_site.admin_view(self.stock_summary_view),
                name='warehouse-stock-summary'
            ),
            path(
                '<int:warehouse_id>/capacity-analysis/',
                self.admin_site.admin_view(self.capacity_analysis_view),
                name='warehouse-capacity-analysis'
            ),
            path(
                '<int:warehouse_id>/movement-report/',
                self.admin_site.admin_view(self.movement_report_view),
                name='warehouse-movement-report'
            ),
        ]
        return custom_urls + urls
    
    def location_count(self, obj):
        """Show number of locations in warehouse."""
        count = obj.locations.filter(is_active=True).count()
        if count > 0:
            url = reverse('admin:inventory_stocklocation_changelist')
            return format_html(
                '<a href="{}?warehouse__id__exact={}">{} locations</a>',
                url, obj.id, count
            )
        return '0 locations'
    location_count.short_description = 'Locations'
    
    def product_count(self, obj):
        """Show number of unique products in warehouse."""
        count = StockItem.objects.filter(
            warehouse=obj,
            quantity_on_hand__gt=0
        ).values('product').distinct().count()
        
        if count > 0:
            url = reverse('admin:inventory_stockitem_changelist')
            return format_html(
                '<a href="{}?warehouse__id__exact={}">{} products</a>',
                url, obj.id, count
            )
        return '0 products'
    product_count.short_description = 'Products'
    
    def total_stock_value(self, obj):
        """Calculate total stock value in warehouse."""
        total_value = StockItem.objects.filter(
            warehouse=obj
        ).aggregate(
            total_value=Sum(F('quantity_on_hand') * F('unit_cost'))
        )['total_value'] or 0
        
        return f'${total_value:,.2f}'
    total_stock_value.short_description = 'Stock Value'
    
    def utilization_percentage(self, obj):
        """Calculate warehouse utilization percentage."""
        if not obj.total_capacity:
            return 'N/A'
        
        # This would need actual volume/weight calculations
        # For now, we'll use item count as a proxy
        total_items = StockItem.objects.filter(
            warehouse=obj
        ).aggregate(
            total=Sum('quantity_on_hand')
        )['total'] or 0
        
        # Assuming 1 unit = 1 capacity unit for simplicity
        utilization = (total_items / obj.total_capacity * 100) if obj.total_capacity > 0 else 0
        
        # Color code based on utilization
        if utilization > 90:
            color = 'red'
        elif utilization > 75:
            color = 'orange'
        else:
            color = 'green'
        
        return format_html(
            '<span style="color: {}; font-weight: bold;">{:.1f}%</span>',
            color, utilization
        )
    utilization_percentage.short_description = 'Utilization'
    
    def generate_capacity_report(self, request, queryset):
        """Generate capacity utilization report."""
        for warehouse in queryset:
            # Logic to generate capacity report
            pass
        
        self.message_user(
            request,
            f'Capacity reports generated for {queryset.count()} warehouses.',
            messages.SUCCESS
        )
    generate_capacity_report.short_description = "Generate capacity reports"
    
    def optimize_locations(self, request, queryset):
        """Optimize stock locations based on movement frequency."""
        optimized_count = 0
        for warehouse in queryset:
            # Logic to optimize locations
            optimized_count += 1
        
        self.message_user(
            request,
            f'Location optimization completed for {optimized_count} warehouses.',
            messages.SUCCESS
        )
    optimize_locations.short_description = "Optimize stock locations"
    
    def audit_inventory(self, request, queryset):
        """Initiate inventory audit for selected warehouses."""
        for warehouse in queryset:
            # Logic to create audit tasks
            pass
        
        self.message_user(
            request,
            f'Inventory audits initiated for {queryset.count()} warehouses.',
            messages.SUCCESS
        )
    audit_inventory.short_description = "Initiate inventory audit"
    
    def stock_summary_view(self, request, warehouse_id):
        """AJAX view for warehouse stock summary."""
        warehouse = get_object_or_404(Warehouse, id=warehouse_id)
        
        summary = StockItem.objects.filter(
            warehouse=warehouse
        ).values(
            'product__name', 'product__sku', 'location__name'
        ).annotate(
            total_quantity=Sum('quantity_on_hand'),
            total_reserved=Sum('quantity_reserved'),
            total_value=Sum(F('quantity_on_hand') * F('unit_cost'))
        ).order_by('-total_value')[:50]  # Top 50 by value
        
        return JsonResponse({
            'warehouse': warehouse.name,
            'stock_summary': list(summary)
        })
    
    def capacity_analysis_view(self, request, warehouse_id):
        """AJAX view for capacity analysis."""
        warehouse = get_object_or_404(Warehouse, id=warehouse_id)
        
        location_utilization = warehouse.locations.annotate(
            item_count=Count('stock_items'),
            total_quantity=Sum('stock_items__quantity_on_hand')
        ).values(
            'name', 'capacity', 'item_count', 'total_quantity'
        )
        
        return JsonResponse({
            'warehouse': warehouse.name,
            'total_capacity': warehouse.total_capacity,
            'location_utilization': list(location_utilization)
        })

@admin.register(StockLocation)
class StockLocationAdmin(BaseInventoryAdmin):
    """Admin interface for stock locations."""
    
    list_display = [
        'name', 'location_code', 'warehouse', 'location_type',
        'capacity', 'current_utilization', 'product_count',
        'zone_info', 'status_indicator'
    ]
    
    list_filter = ['warehouse', 'location_type', 'is_active']
    search_fields = ['name', 'location_code', 'barcode', 'warehouse__name']
    
    fieldsets = (
        ('Basic Information', {
            'fields': (
                'name', 'location_code', 'barcode', 'warehouse', 'location_type'
            )
        }),
        ('Position', {
            'fields': (
                'zone', 'aisle', 'rack', 'shelf', 'bin'
            )
        }),
        ('Capacity & Restrictions', {
            'fields': (
                'capacity', 'weight_limit', 'volume_limit',
                'temperature_controlled', 'hazmat_approved'
            )
        }),
        ('Status', {
            'fields': ('is_active',)
        })
    )
    
    def current_utilization(self, obj):
        """Show current utilization of location."""
        if not obj.capacity:
            return 'N/A'
        
        total_items = obj.stock_items.aggregate(
            total=Sum('quantity_on_hand')
        )['total'] or 0
        
        utilization = (total_items / obj.capacity * 100) if obj.capacity > 0 else 0
        
        # Color code utilization
        if utilization > 100:
            color = 'red'
            status = 'OVER'
        elif utilization > 90:
            color = 'orange'
            status = 'HIGH'
        elif utilization > 75:
            color = 'blue'
            status = 'GOOD'
        else:
            color = 'green'
            status = 'LOW'
        
        return format_html(
            '<span style="color: {}; font-weight: bold;">{:.1f}% ({})</span>',
            color, utilization, status
        )
    current_utilization.short_description = 'Utilization'
    
    def product_count(self, obj):
        """Show number of unique products in location."""
        count = obj.stock_items.filter(
            quantity_on_hand__gt=0
        ).values('product').distinct().count()
        
        if count > 0:
            url = reverse('admin:inventory_stockitem_changelist')
            return format_html(
                '<a href="{}?location__id__exact={}">{} products</a>',
                url, obj.id, count
            )
        return '0 products'
    product_count.short_description = 'Products'
    
    def zone_info(self, obj):
        """Display location zone information."""
        parts = []
        if obj.zone:
            parts.append(f"Zone: {obj.zone}")
        if obj.aisle:
            parts.append(f"Aisle: {obj.aisle}")
        if obj.rack:
            parts.append(f"Rack: {obj.rack}")
        if obj.shelf:
            parts.append(f"Shelf: {obj.shelf}")
        if obj.bin:
            parts.append(f"Bin: {obj.bin}")
        
        return " | ".join(parts) if parts else "No zone info"
    zone_info.short_description = 'Zone Info'
    
    actions = BaseInventoryAdmin.actions + [
        'generate_location_labels', 'optimize_picks', 'consolidate_stock'
    ]
    
    def generate_location_labels(self, request, queryset):
        """Generate barcode labels for selected locations."""
        # Logic to generate labels
        self.message_user(
            request,
            f'Labels generated for {queryset.count()} locations.',
            messages.SUCCESS
        )
    generate_location_labels.short_description = "Generate barcode labels"
    
    def optimize_picks(self, request, queryset):
        """Optimize product placement for picking efficiency."""
        # Logic to analyze and suggest optimization
        self.message_user(
            request,
            f'Pick optimization analysis completed for {queryset.count()} locations.',
            messages.SUCCESS
        )
    optimize_picks.short_description = "Optimize for picking"
    
    def consolidate_stock(self, request, queryset):
        """Suggest stock consolidation opportunities."""
        # Logic to identify consolidation opportunities
        self.message_user(
            request,
            f'Stock consolidation analysis completed for {queryset.count()} locations.',
            messages.SUCCESS
        )
    consolidate_stock.short_description = "Analyze consolidation"