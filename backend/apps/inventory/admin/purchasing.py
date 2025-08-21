# apps/inventory/admin/purchasing.py

from django.contrib import admin
from django.utils.html import format_html
from django.db.models import Count, Sum, F, Q
from django.urls import reverse, path
from django.http import JsonResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.contrib import messages
from django.utils import timezone

from .base import BaseInventoryAdmin, InlineAdminMixin, ReadOnlyInlineMixin
from ..models.purchasing import PurchaseOrder, PurchaseOrderItem, StockReceipt, StockReceiptItem
from ..utils.choices import PO_STATUS_CHOICES, RECEIPT_STATUS_CHOICES

class PurchaseOrderItemInline(InlineAdminMixin, admin.TabularInline):
    """Inline for purchase order items."""
    model = PurchaseOrderItem
    fields = [
        'product', 'variation', 'quantity_ordered', 'unit_cost',
        'total_cost_display', 'quantity_received', 'quantity_pending'
    ]
    readonly_fields = ['total_cost_display', 'quantity_received', 'quantity_pending']
    extra = 1
    
    def total_cost_display(self, obj):
        """Display total cost for line item."""
        if obj.quantity_ordered and obj.unit_cost:
            return f'${(obj.quantity_ordered * obj.unit_cost):,.2f}'
        return '$0.00'
    total_cost_display.short_description = 'Total Cost'
    
    def quantity_received(self, obj):
        """Show quantity received."""
        if obj.id:
            received = obj.receipt_items.aggregate(
                total=Sum('quantity_received')
            )['total'] or 0
            return received
        return 0
    quantity_received.short_description = 'Received'
    
    def quantity_pending(self, obj):
        """Show quantity pending."""
        if obj.id:
            received = obj.receipt_items.aggregate(
                total=Sum('quantity_received')
            )['total'] or 0
            return obj.quantity_ordered - received
        return obj.quantity_ordered if obj.quantity_ordered else 0
    quantity_pending.short_description = 'Pending'

@admin.register(PurchaseOrder)
class PurchaseOrderAdmin(BaseInventoryAdmin):
    """Enhanced admin interface for purchase orders."""
    
    list_display = [
        'po_number', 'supplier', 'order_date', 'status_display',
        'total_amount', 'items_count', 'received_percentage',
        'expected_date', 'days_overdue'
    ]
    
    list_filter = [
        'status', 'warehouse', 'supplier', 
        ('order_date', admin.DateFieldListFilter),
        ('expected_delivery_date', admin.DateFieldListFilter)
    ]
    
    search_fields = [
        'po_number', 'supplier__name', 'reference_number',
        'items__product__name', 'items__product__sku'
    ]
    
    inlines = [PurchaseOrderItemInline]
    
    fieldsets = (
        ('Basic Information', {
            'fields': (
                'po_number', 'supplier', 'warehouse', 'order_date',
                'expected_delivery_date'
            )
        }),
        ('Financial Details', {
            'fields': (
                'subtotal', 'tax_amount', 'shipping_cost', 
                'total_amount_display'
            )
        }),
        ('Status & Tracking', {
            'fields': (
                'status', 'reference_number', 'tracking_number'
            )
        }),
        ('Notes', {
            'fields': ('notes',),
            'classes': ('collapse',)
        })
    )
    
    readonly_fields = ['total_amount_display'] + BaseInventoryAdmin.readonly_fields
    
    actions = BaseInventoryAdmin.actions + [
        'submit_for_approval', 'approve_orders', 'send_to_supplier',
        'mark_received', 'cancel_orders', 'generate_receipts'
    ]
    
    def get_urls(self):
        """Add custom URLs for PO operations."""
        urls = super().get_urls()
        custom_urls = [
            path(
                '<int:po_id>/approve/',
                self.admin_site.admin_view(self.approve_po),
                name='po-approve'
            ),
            path(
                '<int:po_id>/send-email/',
                self.admin_site.admin_view(self.send_po_email),
                name='po-send-email'
            ),
            path(
                '<int:po_id>/receive/',
                self.admin_site.admin_view(self.create_receipt),
                name='po-create-receipt'
            ),
        ]
        return custom_urls + urls
    
    def status_display(self, obj):
        """Show status with color coding."""
        status_colors = {
            'DRAFT': 'gray',
            'PENDING_APPROVAL': 'orange',
            'APPROVED': 'blue',
            'SENT': 'green',
            'PARTIALLY_RECEIVED': 'purple',
            'RECEIVED': 'green',
            'CANCELLED': 'red'
        }
        
        color = status_colors.get(obj.status, 'black')
        
        return format_html(
            '<span style="color: {}; font-weight: bold;">●</span> {}',
            color, obj.get_status_display()
        )
    status_display.short_description = 'Status'
    
    def items_count(self, obj):
        """Show number of line items."""
        count = obj.items.count()
        if count > 0:
            return format_html(
                '<strong>{}</strong> items',
                count
            )
        return '0 items'
    items_count.short_description = 'Items'
    
    def received_percentage(self, obj):
        """Show received percentage."""
        total_ordered = obj.items.aggregate(
            total=Sum('quantity_ordered')
        )['total'] or 0
        
        if total_ordered == 0:
            return '0%'
        
        total_received = 0
        for item in obj.items.all():
            received = item.receipt_items.aggregate(
                total=Sum('quantity_received')
            )['total'] or 0
            total_received += received
        
        percentage = (total_received / total_ordered * 100) if total_ordered > 0 else 0
        
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
    received_percentage.short_description = 'Received'
    
    def days_overdue(self, obj):
        """Calculate days overdue."""
        if not obj.expected_delivery_date:
            return 'N/A'
        
        if obj.status in ['RECEIVED', 'CANCELLED']:
            return 'N/A'
        
        today = timezone.now().date()
        if obj.expected_delivery_date < today:
            days = (today - obj.expected_delivery_date).days
            return format_html(
                '<span style="color: red; font-weight: bold;">{} days</span>',
                days
            )
        else:
            days = (obj.expected_delivery_date - today).days
            return format_html(
                '<span style="color: green;">{} days</span>',
                days
            )
    days_overdue.short_description = 'Days Overdue'
    
    def total_amount_display(self, obj):
        """Display total amount."""
        return f'${obj.total_amount:,.2f}' if obj.total_amount else '$0.00'
    total_amount_display.short_description = 'Total Amount'
    
    def submit_for_approval(self, request, queryset):
        """Submit selected orders for approval."""
        updated = queryset.filter(status='DRAFT').update(status='PENDING_APPROVAL')
        self.message_user(
            request,
            f'{updated} purchase orders submitted for approval.',
            messages.SUCCESS
        )
    submit_for_approval.short_description = "Submit for approval"
    
    def approve_orders(self, request, queryset):
        """Approve selected orders."""
        updated = queryset.filter(status='PENDING_APPROVAL').update(status='APPROVED')
        self.message_user(
            request,
            f'{updated} purchase orders approved.',
            messages.SUCCESS
        )
    approve_orders.short_description = "Approve orders"
    
    def send_to_supplier(self, request, queryset):
        """Send selected orders to suppliers."""
        sent_count = 0
        for po in queryset.filter(status='APPROVED'):
            # Logic to send email to supplier
            po.status = 'SENT'
            po.save()
            sent_count += 1
        
        self.message_user(
            request,
            f'{sent_count} purchase orders sent to suppliers.',
            messages.SUCCESS
        )
    send_to_supplier.short_description = "Send to suppliers"
    
    def approve_po(self, request, po_id):
        """Approve individual PO."""
        po = get_object_or_404(PurchaseOrder, id=po_id)
        
        if po.status == 'PENDING_APPROVAL':
            po.status = 'APPROVED'
            po.approved_by = request.user
            po.approved_date = timezone.now()
            po.save()
            
            messages.success(request, f'Purchase Order {po.po_number} approved.')
        else:
            messages.error(request, f'Cannot approve PO in {po.get_status_display()} status.')
        
        return HttpResponseRedirect(
            reverse('admin:inventory_purchaseorder_change', args=[po_id])
        )
    
    def create_receipt(self, request, po_id):
        """Create receipt for PO."""
        po = get_object_or_404(PurchaseOrder, id=po_id)
        
        # Create receipt logic would go here
        receipt = StockReceipt.objects.create(
            tenant=po.tenant,
            purchase_order=po,
            receipt_number=f'REC-{timezone.now().strftime("%Y%m%d")}-{po.id}',
            supplier=po.supplier,
            warehouse=po.warehouse,
            status='PENDING',
            created_by=request.user
        )
        
        messages.success(
            request, 
            f'Receipt {receipt.receipt_number} created for PO {po.po_number}.'
        )
        
        return HttpResponseRedirect(
            reverse('admin:inventory_stockreceipt_change', args=[receipt.id])
        )

class StockReceiptItemInline(InlineAdminMixin, admin.TabularInline):
    """Inline for stock receipt items."""
    model = StockReceiptItem
    fields = [
        'purchase_order_item', 'quantity_received', 'unit_cost',
        'batch_number', 'expiry_date', 'condition', 'notes'
    ]
    extra = 0

@admin.register(StockReceipt)
class StockReceiptAdmin(BaseInventoryAdmin):
    """Admin interface for stock receipts."""
    
    list_display = [
        'receipt_number', 'purchase_order', 'supplier', 
        'receipt_date', 'status_display', 'items_count',
        'total_received_value'
    ]
    
    list_filter = [
        'status', 'warehouse', 'supplier',
        ('receipt_date', admin.DateFieldListFilter)
    ]
    
    search_fields = [
        'receipt_number', 'purchase_order__po_number',
        'supplier__name', 'tracking_number'
    ]
    
    inlines = [StockReceiptItemInline]
    
    fieldsets = (
        ('Receipt Information', {
            'fields': (
                'receipt_number', 'purchase_order', 'supplier',
                'warehouse', 'receipt_date'
            )
        }),
        ('Shipping Details', {
            'fields': (
                'tracking_number', 'carrier', 'shipped_date', 'delivered_date'
            )
        }),
        ('Status', {
            'fields': ('status', 'quality_check_passed')
        }),
        ('Notes', {
            'fields': ('notes',)
        })
    )
    
    actions = BaseInventoryAdmin.actions + [
        'process_receipts', 'quality_check', 'post_to_inventory'
    ]
    
    def status_display(self, obj):
        """Show status with color coding."""
        status_colors = {
            'PENDING': 'orange',
            'PROCESSING': 'blue',
            'COMPLETED': 'green',
            'REJECTED': 'red'
        }
        
        color = status_colors.get(obj.status, 'black')
        
        return format_html(
            '<span style="color: {}; font-weight: bold;">●</span> {}',
            color, obj.get_status_display()
        )
    status_display.short_description = 'Status'
    
    def items_count(self, obj):
        """Show number of receipt items."""
        return obj.items.count()
    items_count.short_description = 'Items'
    
    def total_received_value(self, obj):
        """Calculate total received value."""
        total = obj.items.aggregate(
            total_value=Sum(F('quantity_received') * F('unit_cost'))
        )['total_value'] or 0
        
        return f'${total:,.2f}'
    total_received_value.short_description = 'Total Value'
    
    def process_receipts(self, request, queryset):
        """Process selected receipts."""
        processed = 0
        for receipt in queryset.filter(status='PENDING'):
            # Logic to process receipt
            receipt.status = 'PROCESSING'
            receipt.save()
            processed += 1
        
        self.message_user(
            request,
            f'{processed} receipts moved to processing.',
            messages.SUCCESS
        )
    process_receipts.short_description = "Process receipts"