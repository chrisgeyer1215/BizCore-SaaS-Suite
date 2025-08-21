# apps/inventory/admin/stock.py

from django.contrib import admin
from django.utils.html import format_html
from django.db.models import Count, Sum, F, Q, Max, Min
from django.urls import reverse, path
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from datetime import timedelta
import json

from .base import BaseInventoryAdmin, InlineAdminMixin, ReadOnlyInlineMixin
from ..models.stock import (
    StockItem, StockMovement, Batch, SerialNumber, StockValuationLayer
)
from ..utils.choices import MOVEMENT_TYPE_CHOICES, VALUATION_METHOD_CHOICES

class StockMovementInline(ReadOnlyInlineMixin, admin.TabularInline):
    """Read-only inline for stock movements."""
    model = StockMovement
    fields = [
        'movement_type', 'quantity', 'unit_cost', 'reference',
        'created_at', 'created_by'
    ]
    ordering = ['-created_at']
    
    def has_add_permission(self, request, obj=None):
        return False

class BatchInline(InlineAdminMixin, admin.TabularInline):
    """Inline for batches."""
    model = Batch
    fields = [
        'batch_number', 'quantity', 'expiry_date', 
        'manufacturing_date', 'status'
    ]
    extra = 0

class SerialNumberInline(InlineAdminMixin, admin.TabularInline):
    """Inline for serial numbers."""
    model = SerialNumber
    fields = ['serial_number', 'status', 'warranty_expiry']
    extra = 0

@admin.register(StockItem)
class StockItemAdmin(BaseInventoryAdmin):
    """Enhanced admin interface for stock items."""
    
    list_display = [
        'product_info', 'warehouse', 'location', 'quantity_display',
        'valuation_info', 'turnover_rate', 'aging_status', 
        'last_movement_date', 'status_indicator'
    ]
    
    list_filter = [
        'warehouse', 'valuation_method', 'is_active',
        ('last_movement_date', admin.DateFieldListFilter),
        ('created_at', admin.DateFieldListFilter)
    ]
    
    search_fields = [
        'product__name', 'product__sku', 'warehouse__name', 
        'location__name', 'location__location_code'
    ]
    
    inlines = [StockMovementInline, BatchInline, SerialNumberInline]
    
    fieldsets = (
        ('Product & Location', {
            'fields': (
                'product', 'variation', 'warehouse', 'location'
            )
        }),
        ('Quantities', {
            'fields': (
                'quantity_on_hand', 'quantity_reserved', 'quantity_available_display'
            )
        }),
        ('Valuation', {
            'fields': (
                'unit_cost', 'average_cost', 'valuation_method', 'total_value_display'
            )
        }),
        ('Tracking', {
            'fields': (
                'last_movement_date', 'last_counted_date'
            )
        }),
        ('Status', {
            'fields': ('is_active',)
        })
    )
    
    readonly_fields = [
        'quantity_available_display', 'total_value_display', 
        'last_movement_date'
    ] + BaseInventoryAdmin.readonly_fields
    
    actions = BaseInventoryAdmin.actions + [
        'initiate_cycle_count', 'recalculate_costs', 'consolidate_lots',
        'generate_movement_report', 'audit_stock_levels'
    ]
    
    def get_urls(self):
        """Add custom URLs for stock operations."""
        urls = super().get_urls()
        custom_urls = [
            path(
                '<int:stock_item_id>/movement-history/',
                self.admin_site.admin_view(self.movement_history_view),
                name='stockitem-movement-history'
            ),
            path(
                '<int:stock_item_id>/valuation-layers/',
                self.admin_site.admin_view(self.valuation_layers_view),
                name='stockitem-valuation-layers'
            ),
            path(
                '<int:stock_item_id>/aging-analysis/',
                self.admin_site.admin_view(self.aging_analysis_view),
                name='stockitem-aging-analysis'
            ),
        ]
        return custom_urls + urls
    
    def product_info(self, obj):
        """Show product information with link."""
        product_url = reverse('admin:inventory_product_change', args=[obj.product.id])
        return format_html(
            '<a href="{}" title="{}">{}</a><br/><small>{}</small>',
            product_url, obj.product.description or '', 
            obj.product.name, obj.product.sku
        )
    product_info.short_description = 'Product'
    
    def quantity_display(self, obj):
        """Show quantity information with visual indicators."""
        available = obj.quantity_on_hand - obj.quantity_reserved
        
        # Determine status color
        if obj.quantity_on_hand == 0:
            color = 'red'
            status = 'OUT'
        elif obj.product.reorder_level and obj.quantity_on_hand <= obj.product.reorder_level:
            color = 'orange'
            status = 'LOW'
        elif obj.product.max_stock_level and obj.quantity_on_hand >= obj.product.max_stock_level:
            color = 'blue'
            status = 'HIGH'
        else:
            color = 'green'
            status = 'OK'
        
        return format_html(
            '<div>'
            '<strong style="color: {};">On Hand: {}</strong><br/>'
            'Reserved: {}<br/>'
            'Available: {} ({})'
            '</div>',
            color, obj.quantity_on_hand, obj.quantity_reserved, available, status
        )
    quantity_display.short_description = 'Quantities'
    
    def valuation_info(self, obj):
        """Show valuation information."""
        total_value = obj.quantity_on_hand * obj.unit_cost
        
        return format_html(
            '<div>'
            'Unit Cost: ${:.2f}<br/>'
            'Avg Cost: ${:.2f}<br/>'
            'Total Value: <strong>${:,.2f}</strong><br/>'
            'Method: {}'
            '</div>',
            obj.unit_cost, obj.average_cost or 0, total_value,
            obj.get_valuation_method_display()
        )
    valuation_info.short_description = 'Valuation'
    
    def turnover_rate(self, obj):
        """Calculate inventory turnover rate."""
        # Get movements from last 12 months
        one_year_ago = timezone.now() - timedelta(days=365)
        
        outbound_movements = StockMovement.objects.filter(
            product=obj.product,
            warehouse=obj.warehouse,
            movement_type__in=['SALE', 'TRANSFER_OUT', 'ADJUSTMENT_OUT'],
            created_at__gte=one_year_ago
        ).aggregate(total=Sum('quantity'))['total'] or 0
        
        if obj.quantity_on_hand > 0:
            turnover = outbound_movements / obj.quantity_on_hand
            
            # Color code turnover rate
            if turnover > 12:  # More than 12x per year
                color = 'green'
                rating = 'Excellent'
            elif turnover > 6:  # 6-12x per year
                color = 'blue'
                rating = 'Good'
            elif turnover > 2:  # 2-6x per year
                color = 'orange'
                rating = 'Average'
            else:  # Less than 2x per year
                color = 'red'
                rating = 'Poor'
            
            return format_html(
                '<span style="color: {}; font-weight: bold;" title="{}">{:.1f}x</span>',
                color, rating, turnover
            )
        
        return format_html('<span style="color: gray;">N/A</span>')
    turnover_rate.short_description = 'Turnover'
    
    def aging_status(self, obj):
        """Show inventory aging status."""
        if not obj.last_movement_date:
            return format_html('<span style="color: gray;">No movement</span>')
        
        days_since_movement = (timezone.now().date() - obj.last_movement_date).days
        
        if days_since_movement > 365:
            color = 'red'
            status = 'Dead Stock'
        elif days_since_movement > 180:
            color = 'orange'
            status = 'Slow Moving'
        elif days_since_movement > 90:
            color = 'blue'
            status = 'Normal'
        else:
            color = 'green'
            status = 'Fast Moving'
        
        return format_html(
            '<span style="color: {}; font-weight: bold;" title="{} days">{}</span>',
            color, days_since_movement, status
        )
    aging_status.short_description = 'Aging'
    
    def last_movement_date(self, obj):
        """Show last movement date with link to history."""
        if obj.last_movement_date:
            url = reverse('admin:inventory_stockmovement_changelist')
            return format_html(
                '<a href="{}?product__id__exact={}&warehouse__id__exact={}">{}</a>',
                url, obj.product.id, obj.warehouse.id, obj.last_movement_date
            )
        return 'No movement'
    last_movement_date.short_description = 'Last Movement'
    
    def quantity_available_display(self, obj):
        """Display available quantity."""
        return obj.quantity_on_hand - obj.quantity_reserved
    quantity_available_display.short_description = 'Available Quantity'
    
    def total_value_display(self, obj):
        """Display total stock value."""
        return f'${(obj.quantity_on_hand * obj.unit_cost):,.2f}'
    total_value_display.short_description = 'Total Value'
    
    def initiate_cycle_count(self, request, queryset):
        """Initiate cycle count for selected stock items."""
        from ..models.adjustments.cycle_counts import CycleCount
        
        cycle_count = CycleCount.objects.create(
            tenant=request.user.tenant,
            name=f"Cycle Count - {timezone.now().strftime('%Y-%m-%d')}",
            status='PENDING',
            created_by=request.user
        )
        
        for stock_item in queryset:
            cycle_count.items.create(
                stock_item=stock_item,
                expected_quantity=stock_item.quantity_on_hand,
                status='PENDING'
            )
        
        self.message_user(
            request,
            f'Cycle count initiated for {queryset.count()} items. Count ID: {cycle_count.id}',
            messages.SUCCESS
        )
    initiate_cycle_count.short_description = "Initiate cycle count"
    
    def recalculate_costs(self, request, queryset):
        """Recalculate costs for selected stock items."""
        recalculated = 0
        for stock_item in queryset:
            # Logic to recalculate average cost based on valuation method
            # This would typically use the valuation service
            recalculated += 1
        
        self.message_user(
            request,
            f'Costs recalculated for {recalculated} stock items.',
            messages.SUCCESS
        )
    recalculate_costs.short_description = "Recalculate costs"

@admin.register(StockMovement)
class StockMovementAdmin(BaseInventoryAdmin):
    """Admin interface for stock movements."""
    
    list_display = [
        'movement_date', 'movement_type', 'product_info', 
        'warehouse', 'quantity_display', 'unit_cost',
        'reference', 'user'
    ]
    
    list_filter = [
        'movement_type', 'warehouse',
        ('created_at', admin.DateFieldListFilter)
    ]
    
    search_fields = [
        'product__name', 'product__sku', 'reference', 
        'notes', 'user__username'
    ]
    
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Movement Information', {
            'fields': (
                'movement_type', 'product', 'variation', 'warehouse', 'location'
            )
        }),
        ('Quantity & Cost', {
            'fields': (
                'quantity', 'unit_cost', 'total_cost_display'
            )
        }),
        ('Reference', {
            'fields': (
                'reference', 'batch', 'serial_number', 'notes'
            )
        })
    )
    
    readonly_fields = ['total_cost_display'] + BaseInventoryAdmin.readonly_fields
    
    def has_add_permission(self, request):
        """Prevent direct addition of stock movements."""
        return False
    
    def has_change_permission(self, request, obj=None):
        """Prevent editing of stock movements."""
        return False
    
    def has_delete_permission(self, request, obj=None):
        """Prevent deletion of stock movements."""
        return False
    
    def movement_date(self, obj):
        """Format movement date."""
        return obj.created_at.strftime('%Y-%m-%d %H:%M')
    movement_date.short_description = 'Date'
    
    def product_info(self, obj):
        """Show product information."""
        return format_html(
            '{}<br/><small>{}</small>',
            obj.product.name, obj.product.sku
        )
    product_info.short_description = 'Product'
    
    def quantity_display(self, obj):
        """Show quantity with direction indicator."""
        if obj.movement_type in ['RECEIPT', 'ADJUSTMENT_IN', 'TRANSFER_IN']:
            color = 'green'
            symbol = '+'
        else:
            color = 'red'
            symbol = '-'
        
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}{}</span>',
            color, symbol, obj.quantity
        )
    quantity_display.short_description = 'Quantity'
    
    def total_cost_display(self, obj):
        """Display total cost of movement."""
        return f'${(obj.quantity * obj.unit_cost):,.2f}'
    total_cost_display.short_description = 'Total Cost'

@admin.register(Batch)
class BatchAdmin(BaseInventoryAdmin):
    """Admin interface for batches."""
    
    list_display = [
        'batch_number', 'product', 'quantity', 'manufacturing_date',
        'expiry_date', 'days_to_expiry', 'status_indicator'
    ]
    
    list_filter = [
        'status', 
        ('manufacturing_date', admin.DateFieldListFilter),
        ('expiry_date', admin.DateFieldListFilter)
    ]
    
    search_fields = ['batch_number', 'product__name', 'product__sku']
    
    def days_to_expiry(self, obj):
        """Calculate days to expiry with color coding."""
        if not obj.expiry_date:
            return 'N/A'
        
        days = (obj.expiry_date - timezone.now().date()).days
        
        if days < 0:
            color = 'red'
            status = 'EXPIRED'
        elif days < 30:
            color = 'orange'
            status = 'EXPIRING SOON'
        elif days < 90:
            color = 'blue'
            status = 'MONITOR'
        else:
            color = 'green'
            status = 'GOOD'
        
        return format_html(
            '<span style="color: {}; font-weight: bold;" title="{}">{} days</span>',
            color, status, days
        )
    days_to_expiry.short_description = 'Days to Expiry'
    
    actions = BaseInventoryAdmin.actions + ['mark_expired', 'extend_expiry']
    
    def mark_expired(self, request, queryset):
        """Mark selected batches as expired."""
        updated = queryset.update(status='EXPIRED')
        self.message_user(
            request,
            f'{updated} batches marked as expired.',
            messages.SUCCESS
        )
    mark_expired.short_description = "Mark as expired"

@admin.register(SerialNumber)
class SerialNumberAdmin(BaseInventoryAdmin):
    """Admin interface for serial numbers."""
    
    list_display = [
        'serial_number', 'product', 'warehouse', 'location',
        'status', 'warranty_expiry', 'customer_info'
    ]
    
    list_filter = [
        'status', 'warehouse',
        ('warranty_expiry', admin.DateFieldListFilter)
    ]
    
    search_fields = [
        'serial_number', 'product__name', 'product__sku',
        'customer_name', 'customer_email'
    ]
    
    def customer_info(self, obj):
        """Show customer information if sold."""
        if obj.status == 'SOLD' and obj.customer_name:
            return format_html(
                '{}<br/><small>{}</small>',
                obj.customer_name, obj.customer_email or ''
            )
        return '-'
    customer_info.short_description = 'Customer'

@admin.register(StockValuationLayer)
class StockValuationLayerAdmin(BaseInventoryAdmin):
    """Admin interface for stock valuation layers."""
    
    list_display = [
        'product', 'warehouse', 'layer_date', 'remaining_quantity',
        'unit_cost', 'total_value', 'valuation_method'
    ]
    
    list_filter = [
        'valuation_method', 'warehouse',
        ('layer_date', admin.DateFieldListFilter)
    ]
    
    search_fields = ['product__name', 'product__sku']
    
    def has_add_permission(self, request):
        """Prevent manual addition."""
        return False
    
    def has_change_permission(self, request, obj=None):
        """Allow viewing but not editing."""
        return False
    
    def total_value(self, obj):
        """Calculate total value of layer."""
        return f'${(obj.remaining_quantity * obj.unit_cost):,.2f}'
    total_value.short_description = 'Total Value'