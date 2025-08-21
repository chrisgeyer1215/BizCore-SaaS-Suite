# apps/inventory/admin/transfers.py

from django.contrib import admin
from django.utils.html import format_html
from django.db.models import Count, Sum, F, Q
from django.urls import reverse, path
from django.http import JsonResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.contrib import messages
from django.utils import timezone

from .base import BaseInventoryAdmin, InlineAdminMixin, ReadOnlyInlineMixin
from ..models.transfers import StockTransfer, StockTransferItem
from ..utils.choices import TRANSFER_STATUS_CHOICES

class StockTransferItemInline(InlineAdminMixin, admin.TabularInline):
    """Inline for stock transfer items."""
    model = StockTransferItem
    fields = [
        'product', 'variation', 'batch', 'quantity_requested',
        'quantity_shipped', 'quantity_received', 'unit_cost',
        'from_location', 'to_location', 'condition'
    ]
    readonly_fields = ['quantity_shipped', 'quantity_received']
    extra = 1
    
    def get_queryset(self, request):
        """Optimize queryset with related fields."""
        return super().get_queryset(request).select_related(
            'product', 'variation', 'batch', 'from_location', 'to_location'
        )

@admin.register(StockTransfer)
class StockTransferAdmin(BaseInventoryAdmin):
    """Enhanced admin interface for stock transfers."""
    
    list_display = [
        'transfer_number', 'from_warehouse', 'to_warehouse',
        'transfer_date', 'status_display', 'items_count',
        'total_value', 'completion_percentage', 'priority_display',
        'expected_date', 'days_in_transit'
    ]
    
    list_filter = [
        'status', 'priority', 'transfer_type',
        'from_warehouse', 'to_warehouse',
        ('transfer_date', admin.DateFieldListFilter),
        ('expected_delivery_date', admin.DateFieldListFilter)
    ]
    
    search_fields = [
        'transfer_number', 'reference_number',
        'items__product__name', 'items__product__sku',
        'requested_by__username', 'approved_by__username'
    ]
    
    inlines = [StockTransferItemInline]
    
    fieldsets = (
        ('Transfer Information', {
            'fields': (
                'transfer_number', 'transfer_type', 'priority',
                'from_warehouse', 'to_warehouse'
            )
        }),
        ('Dates & Timeline', {
            'fields': (
                'transfer_date', 'expected_delivery_date',
                'shipped_date', 'delivered_date'
            )
        }),
        ('Approval & Tracking', {
            'fields': (
                'status', 'requested_by', 'approved_by', 'approved_date',
                'tracking_number', 'carrier'
            )
        }),
        ('Financial', {
            'fields': (
                'total_cost', 'shipping_cost', 'insurance_cost'
            )
        }),
        ('Reference & Notes', {
            'fields': (
                'reference_number', 'reason', 'notes'
            ),
            'classes': ('collapse',)
        })
    )
    
    readonly_fields = BaseInventoryAdmin.readonly_fields + [
        'approved_by', 'approved_date'
    ]
    
    actions = BaseInventoryAdmin.actions + [
        'submit_for_approval', 'approve_transfers', 'ship_transfers',
        'mark_delivered', 'cancel_transfers', 'generate_shipping_labels'
    ]
    
    def get_urls(self):
        """Add custom URLs for transfer operations."""
        urls = super().get_urls()
        custom_urls = [
            path(
                '<int:transfer_id>/approve/',
                self.admin_site.admin_view(self.approve_transfer),
                name='transfer-approve'
            ),
            path(
                '<int:transfer_id>/ship/',
                self.admin_site.admin_view(self.ship_transfer),
                name='transfer-ship'
            ),
            path(
                '<int:transfer_id>/receive/',
                self.admin_site.admin_view(self.receive_transfer),
                name='transfer-receive'
            ),
            path(
                '<int:transfer_id>/tracking/',
                self.admin_site.admin_view(self.tracking_info),
                name='transfer-tracking'
            ),
        ]
        return custom_urls + urls
    
    def status_display(self, obj):
        """Show status with color coding and progress."""
        status_colors = {
            'REQUESTED': 'orange',
            'APPROVED': 'blue',
            'IN_TRANSIT': 'purple',
            'DELIVERED': 'green',
            'CANCELLED': 'red',
            'REJECTED': 'red'
        }
        
        color = status_colors.get(obj.status, 'black')
        
        # Add workflow indicators
        workflow_steps = ['REQUESTED', 'APPROVED', 'IN_TRANSIT', 'DELIVERED']
        current_step = workflow_steps.index(obj.status) + 1 if obj.status in workflow_steps else 0
        total_steps = len(workflow_steps)
        
        progress_bar = '●' * current_step + '○' * (total_steps - current_step)
        
        return format_html(
            '<div>'
            '<span style="color: {}; font-weight: bold;">●</span> {}<br/>'
            '<small title="Progress: {}/{}">{}</small>'
            '</div>',
            color, obj.get_status_display(), 
            current_step, total_steps, progress_bar
        )
    status_display.short_description = 'Status & Progress'
    
    def items_count(self, obj):
        """Show number of transfer items."""
        count = obj.items.count()
        if count > 0:
            total_qty = obj.items.aggregate(
                total=Sum('quantity_requested')
            )['total'] or 0
            return format_html(
                '<strong>{}</strong> items<br/><small>{} units</small>',
                count, total_qty
            )
        return '0 items'
    items_count.short_description = 'Items'
    
    def total_value(self, obj):
        """Calculate total transfer value."""
        total = obj.items.aggregate(
            total_value=Sum(F('quantity_requested') * F('unit_cost'))
        )['total_value'] or 0
        
        return f'${total:,.2f}'
    total_value.short_description = 'Total Value'
    
    def completion_percentage(self, obj):
        """Show transfer completion percentage."""
        items = obj.items.all()
        if not items:
            return '0%'
        
        total_requested = sum(item.quantity_requested for item in items)
        total_received = sum(item.quantity_received for item in items)
        
        if total_requested == 0:
            return '0%'
        
        percentage = (total_received / total_requested * 100)
        
        # Color code percentage
        if percentage == 100:
            color = 'green'
        elif percentage > 0:
            color = 'orange'
        else:
            color = 'red'
        
        return format_html(
            '<span style="color: {}; font-weight: bold;">{:.1f}%</span>',
            color, percentage
        )
    completion_percentage.short_description = 'Complete'
    
    def priority_display(self, obj):
        """Show priority with visual indicator."""
        priority_colors = {
            'LOW': 'green',
            'NORMAL': 'blue',
            'HIGH': 'orange',
            'URGENT': 'red'
        }
        
        color = priority_colors.get(obj.priority, 'black')
        icons = {
            'LOW': '▼',
            'NORMAL': '■',
            'HIGH': '▲',
            'URGENT': '🔥'
        }
        
        return format_html(
            '<span style="color: {}; font-weight: bold;">{} {}</span>',
            color, icons.get(obj.priority, '■'), obj.get_priority_display()
        )
    priority_display.short_description = 'Priority'
    
    def days_in_transit(self, obj):
        """Calculate days in transit."""
        if obj.status == 'IN_TRANSIT' and obj.shipped_date:
            days = (timezone.now().date() - obj.shipped_date).days
            
            # Color code based on expected delivery
            if obj.expected_delivery_date:
                overdue = timezone.now().date() > obj.expected_delivery_date
                color = 'red' if overdue else 'green'
            else:
                color = 'blue'
            
            return format_html(
                '<span style="color: {}; font-weight: bold;">{} days</span>',
                color, days
            )
        elif obj.status == 'DELIVERED' and obj.shipped_date and obj.delivered_date:
            days = (obj.delivered_date - obj.shipped_date).days
            return format_html(
                '<span style="color: green;">{} days</span>',
                days
            )
        
        return 'N/A'
    days_in_transit.short_description = 'Transit Time'
    
    def submit_for_approval(self, request, queryset):
        """Submit transfers for approval."""
        updated = queryset.filter(status='REQUESTED').update(status='PENDING_APPROVAL')
        self.message_user(
            request,
            f'{updated} transfers submitted for approval.',
            messages.SUCCESS
        )
    submit_for_approval.short_description = "Submit for approval"
    
    def approve_transfers(self, request, queryset):
        """Approve selected transfers."""
        approved = 0
        for transfer in queryset.filter(status__in=['REQUESTED', 'PENDING_APPROVAL']):
            transfer.status = 'APPROVED'
            transfer.approved_by = request.user
            transfer.approved_date = timezone.now()
            transfer.save()
            approved += 1
        
        self.message_user(
            request,
            f'{approved} transfers approved.',
            messages.SUCCESS
        )
    approve_transfers.short_description = "Approve transfers"
    
    def ship_transfers(self, request, queryset):
        """Mark transfers as shipped."""
        shipped = 0
        for transfer in queryset.filter(status='APPROVED'):
            transfer.status = 'IN_TRANSIT'
            transfer.shipped_date = timezone.now().date()
            transfer.save()
            
            # Update item quantities shipped
            for item in transfer.items.all():
                if item.quantity_shipped == 0:
                    item.quantity_shipped = item.quantity_requested
                    item.save()
            
            shipped += 1
        
        self.message_user(
            request,
            f'{shipped} transfers marked as shipped.',
            messages.SUCCESS
        )
    ship_transfers.short_description = "Mark as shipped"
    
    def mark_delivered(self, request, queryset):
        """Mark transfers as delivered."""
        delivered = 0
        for transfer in queryset.filter(status='IN_TRANSIT'):
            transfer.status = 'DELIVERED'
            transfer.delivered_date = timezone.now().date()
            transfer.save()
            
            # Update item quantities received
            for item in transfer.items.all():
                if item.quantity_received == 0:
                    item.quantity_received = item.quantity_shipped
                    item.save()
            
            delivered += 1
        
        self.message_user(
            request,
            f'{delivered} transfers marked as delivered.',
            messages.SUCCESS
        )
    mark_delivered.short_description = "Mark as delivered"
    
    def approve_transfer(self, request, transfer_id):
        """Approve individual transfer."""
        transfer = get_object_or_404(StockTransfer, id=transfer_id)
        
        if transfer.status in ['REQUESTED', 'PENDING_APPROVAL']:
            transfer.status = 'APPROVED'
            transfer.approved_by = request.user
            transfer.approved_date = timezone.now()
            transfer.save()
            
            messages.success(
                request, 
                f'Transfer {transfer.transfer_number} approved.'
            )
        else:
            messages.error(
                request, 
                f'Cannot approve transfer in {transfer.get_status_display()} status.'
            )
        
        return HttpResponseRedirect(
            reverse('admin:inventory_stocktransfer_change', args=[transfer_id])
        )
    
    def tracking_info(self, request, transfer_id):
        """Get tracking information."""
        transfer = get_object_or_404(StockTransfer, id=transfer_id)
        
        # This would integrate with carrier APIs for real tracking
        tracking_data = {
            'transfer_number': transfer.transfer_number,
            'tracking_number': transfer.tracking_number,
            'carrier': transfer.carrier,
            'status': transfer.status,
            'shipped_date': transfer.shipped_date.isoformat() if transfer.shipped_date else None,
            'expected_date': transfer.expected_delivery_date.isoformat() if transfer.expected_delivery_date else None,
            'delivered_date': transfer.delivered_date.isoformat() if transfer.delivered_date else None
        }
        
        return JsonResponse(tracking_data)