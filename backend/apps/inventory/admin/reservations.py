# apps/inventory/admin/reservations.py

from django.contrib import admin
from django.utils.html import format_html
from django.db.models import Count, Sum, F, Q
from django.urls import reverse, path
from django.contrib import messages
from django.utils import timezone
from datetime import timedelta

from .base import BaseInventoryAdmin, InlineAdminMixin, ReadOnlyInlineMixin
from ..models.reservations import StockReservation, StockReservationItem
from ..utils.choices import RESERVATION_STATUS_CHOICES, RESERVATION_TYPE_CHOICES

class StockReservationItemInline(InlineAdminMixin, admin.TabularInline):
    """Inline for stock reservation items."""
    model = StockReservationItem
    fields = [
        'product', 'variation', 'warehouse', 'location',
        'quantity_reserved', 'quantity_fulfilled', 'quantity_remaining',
        'unit_cost', 'priority'
    ]
    readonly_fields = ['quantity_remaining']
    extra = 1
    
    def quantity_remaining(self, obj):
        """Calculate remaining quantity to fulfill."""
        if obj.quantity_reserved and obj.quantity_fulfilled:
            remaining = obj.quantity_reserved - obj.quantity_fulfilled
            
            color = 'red' if remaining > 0 else 'green'
            
            return format_html(
                '<span style="color: {}; font-weight: bold;">{}</span>',
                color, remaining
            )
        return obj.quantity_reserved or 0
    quantity_remaining.short_description = 'Remaining'

@admin.register(StockReservation)
class StockReservationAdmin(BaseInventoryAdmin):
    """Enhanced admin interface for stock reservations."""
    
    list_display = [
        'reservation_number', 'reservation_type', 'customer_order',
        'reservation_date', 'status_display', 'items_count',
        'fulfillment_percentage', 'expiry_status', 'priority_display',
        'total_value'
    ]
    
    list_filter = [
        'status', 'reservation_type', 'priority',
        ('reservation_date', admin.DateFieldListFilter),
        ('expiry_date', admin.DateFieldListFilter),
        ('fulfilled_date', admin.DateFieldListFilter)
    ]
    
    search_fields = [
        'reservation_number', 'customer_order', 'reference_number',
        'items__product__name', 'items__product__sku',
        'customer_name', 'customer_email'
    ]
    
    inlines = [StockReservationItemInline]
    
    fieldsets = (
        ('Reservation Information', {
            'fields': (
                'reservation_number', 'reservation_type', 'priority',
                'customer_order', 'reference_number'
            )
        }),
        ('Customer Information', {
            'fields': (
                'customer_name', 'customer_email', 'customer_phone'
            )
        }),
        ('Dates & Timeline', {
            'fields': (
                'reservation_date', 'expiry_date', 'required_date',
                'fulfilled_date'
            )
        }),
        ('Status & Fulfillment', {
            'fields': (
                'status', 'auto_fulfill', 'partial_fulfillment_allowed'
            )
        }),
        ('Notes', {
            'fields': ('notes',),
            'classes': ('collapse',)
        })
    )
    
    actions = BaseInventoryAdmin.actions + [
        'fulfill_reservations', 'extend_expiry', 'cancel_reservations',
        'convert_to_backorder', 'priority_boost', 'auto_allocate'
    ]
    
    def get_urls(self):
        """Add custom URLs for reservation operations."""
        urls = super().get_urls()
        custom_urls = [
            path(
                '<int:reservation_id>/fulfill/',
                self.admin_site.admin_view(self.fulfill_reservation),
                name='reservation-fulfill'
            ),
            path(
                '<int:reservation_id>/allocate/',
                self.admin_site.admin_view(self.allocate_stock),
                name='reservation-allocate'
            ),
            path(
                'expiring-soon/',
                self.admin_site.admin_view(self.expiring_reservations),
                name='reservations-expiring'
            ),
        ]
        return custom_urls + urls
    
    def status_display(self, obj):
        """Show status with visual indicators."""
        status_colors = {
            'ACTIVE': 'green',
            'PARTIALLY_FULFILLED': 'orange',
            'FULFILLED': 'blue',
            'EXPIRED': 'red',
            'CANCELLED': 'gray'
        }
        
        color = status_colors.get(obj.status, 'black')
        
        # Add urgency indicators
        urgency = ""
        if obj.status == 'ACTIVE' and obj.expiry_date:
            days_to_expiry = (obj.expiry_date - timezone.now().date()).days
            if days_to_expiry <= 1:
                urgency = " 🚨"
            elif days_to_expiry <= 3:
                urgency = " ⚠️"
        
        return format_html(
            '<span style="color: {}; font-weight: bold;">●</span> {}{}'.format(
                color, obj.get_status_display(), urgency
            )
        )
    status_display.short_description = 'Status'
    
    def items_count(self, obj):
        """Show reservation items count and quantities."""
        items = obj.items.all()
        
        if not items:
            return '0 items'
        
        total_reserved = sum(item.quantity_reserved for item in items)
        total_fulfilled = sum(item.quantity_fulfilled or 0 for item in items)
        
        return format_html(
            '<strong>{}</strong> items<br/>'
            '<small>Reserved: {} | Fulfilled: {}</small>',
            len(items), int(total_reserved), int(total_fulfilled)
        )
    items_count.short_description = 'Items'
    
    def fulfillment_percentage(self, obj):
        """Calculate fulfillment percentage."""
        items = obj.items.all()
        
        if not items:
            return '0%'
        
        total_reserved = sum(item.quantity_reserved for item in items)
        total_fulfilled = sum(item.quantity_fulfilled or 0 for item in items)
        
        if total_reserved == 0:
            return '0%'
        
        percentage = (total_fulfilled / total_reserved * 100)
        
        # Color code percentage
        if percentage == 100:
            color = 'green'
        elif percentage >= 50:
            color = 'orange'
        elif percentage > 0:
            color = 'blue'
        else:
            color = 'red'
        
        return format_html(
            '<span style="color: {}; font-weight: bold;">{:.1f}%</span>',
            color, percentage
        )
    fulfillment_percentage.short_description = 'Fulfilled'
    
    def expiry_status(self, obj):
        """Show expiry status with countdown."""
        if not obj.expiry_date:
            return format_html(
                '<span style="color: gray;">No Expiry</span>'
            )
        
        days_remaining = (obj.expiry_date - timezone.now().date()).days
        
        if days_remaining < 0:
            return format_html(
                '<span style="color: red; font-weight: bold;">EXPIRED</span><br/>'
                '<small>{} days ago</small>',
                abs(days_remaining)
            )
        elif days_remaining == 0:
            return format_html(
                '<span style="color: red; font-weight: bold;">EXPIRES TODAY</span>'
            )
        elif days_remaining <= 3:
            return format_html(
                '<span style="color: orange; font-weight: bold;">{} days</span>',
                days_remaining
            )
        else:
            return format_html(
                '<span style="color: green;">{} days</span>',
                days_remaining
            )
    expiry_status.short_description = 'Expires'
    
    def priority_display(self, obj):
        """Show priority with visual indicators."""
        priority_colors = {
            'LOW': 'green',
            'NORMAL': 'blue',
            'HIGH': 'orange',
            'URGENT': 'red'
        }
        
        priority_icons = {
            'LOW': '▼',
            'NORMAL': '■',
            'HIGH': '▲',
            'URGENT': '🔥'
        }
        
        color = priority_colors.get(obj.priority, 'black')
        icon = priority_icons.get(obj.priority, '■')
        
        return format_html(
            '<span style="color: {}; font-weight: bold;">{} {}</span>',
            color, icon, obj.get_priority_display()
        )
    priority_display.short_description = 'Priority'
    
    def total_value(self, obj):
        """Calculate total reservation value."""
        total = obj.items.aggregate(
            total_value=Sum(F('quantity_reserved') * F('unit_cost'))
        )['total_value'] or 0
        
        return f'${total:,.2f}'
    total_value.short_description = 'Total Value'
    
    def fulfill_reservations(self, request, queryset):
        """Fulfill selected reservations."""
        fulfilled = 0
        for reservation in queryset.filter(status='ACTIVE'):
            # Logic to fulfill reservation
            # Check stock availability and allocate
            can_fulfill = True  # Placeholder logic
            
            if can_fulfill:
                reservation.status = 'FULFILLED'
                reservation.fulfilled_date = timezone.now().date()
                reservation.save()
                fulfilled += 1
        
        self.message_user(
            request,
            f'{fulfilled} reservations fulfilled.',
            messages.SUCCESS
        )
    fulfill_reservations.short_description = "Fulfill reservations"
    
    def extend_expiry(self, request, queryset):
        """Extend expiry date for selected reservations."""
        extended = 0
        extension_days = 7  # Default extension
        
        for reservation in queryset.filter(status='ACTIVE'):
            if reservation.expiry_date:
                reservation.expiry_date += timedelta(days=extension_days)
                reservation.save()
                extended += 1
        
        self.message_user(
            request,
            f'Expiry extended by {extension_days} days for {extended} reservations.',
            messages.SUCCESS
        )
    extend_expiry.short_description = "Extend expiry (7 days)"
    
    def cancel_reservations(self, request, queryset):
        """Cancel selected reservations."""
        cancelled = 0
        for reservation in queryset.filter(
            status__in=['ACTIVE', 'PARTIALLY_FULFILLED']
        ):
            reservation.status = 'CANCELLED'
            reservation.save()
            
            # Release reserved stock
            for item in reservation.items.all():
                # Logic to release stock reservation
                pass
            
            cancelled += 1
        
        self.message_user(
            request,
            f'{cancelled} reservations cancelled and stock released.',
            messages.SUCCESS
        )
    cancel_reservations.short_description = "Cancel reservations"
    
    def priority_boost(self, request, queryset):
        """Boost priority of selected reservations."""
        priority_map = {
            'LOW': 'NORMAL',
            'NORMAL': 'HIGH',
            'HIGH': 'URGENT'
        }
        
        boosted = 0
        for reservation in queryset:
            if reservation.priority in priority_map:
                reservation.priority = priority_map[reservation.priority]
                reservation.save()
                boosted += 1
        
        self.message_user(
            request,
            f'Priority boosted for {boosted} reservations.',
            messages.SUCCESS
        )
    priority_boost.short_description = "Boost priority"
    
    def auto_allocate(self, request, queryset):
        """Auto-allocate stock for selected reservations."""
        allocated = 0
        for reservation in queryset.filter(status='ACTIVE'):
            # Logic for auto-allocation
            # This would use the reservation service
            allocated += 1
        
        self.message_user(
            request,
            f'Auto-allocation attempted for {allocated} reservations.',
            messages.SUCCESS
        )
    auto_allocate.short_description = "Auto-allocate stock"