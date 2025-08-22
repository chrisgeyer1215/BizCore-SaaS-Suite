# apps/inventory/admin/workflows/replenishment.py

from django.contrib import admin
from django.utils.html import format_html
from django.db.models import Count, Sum, F, Q, Min, Max
from django.urls import reverse, path
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.contrib import messages
from django.utils import timezone
from datetime import timedelta

from ..base import BaseInventoryAdmin
from ...models.catalog.products import Product
from ...models.stock.items import StockItem
from ...models.purchasing.orders import PurchaseOrder
from ...services.stock.reorder_service import ReorderService

class ReplenishmentRecommendation(models.Model):
    """Model for replenishment recommendations."""
    tenant = models.ForeignKey('core.Tenant', on_delete=models.CASCADE)
    product = models.ForeignKey('inventory.Product', on_delete=models.CASCADE)
    warehouse = models.ForeignKey('inventory.Warehouse', on_delete=models.CASCADE)
    
    current_stock = models.DecimalField(max_digits=15, decimal_places=4)
    reorder_level = models.DecimalField(max_digits=15, decimal_places=4)
    max_stock_level = models.DecimalField(max_digits=15, decimal_places=4)
    
    recommended_quantity = models.DecimalField(max_digits=15, decimal_places=4)
    recommended_supplier = models.ForeignKey('inventory.Supplier', on_delete=models.SET_NULL, null=True)
    
    priority = models.CharField(
        max_length=20,
        choices=[
            ('CRITICAL', 'Critical'),
            ('HIGH', 'High'),
            ('MEDIUM', 'Medium'),
            ('LOW', 'Low')
        ],
        default='MEDIUM'
    )
    
    status = models.CharField(
        max_length=20,
        choices=[
            ('PENDING', 'Pending'),
            ('APPROVED', 'Approved'),
            ('ORDERED', 'Ordered'),
            ('REJECTED', 'Rejected')
        ],
        default='PENDING'
    )
    
    estimated_cost = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    lead_time_days = models.IntegerField(default=0)
    demand_forecast = models.JSONField(default=dict)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True)
    
    class Meta:
        unique_together = ['tenant', 'product', 'warehouse']
        indexes = [
            models.Index(fields=['tenant', 'priority', 'status']),
            models.Index(fields=['created_at']),
        ]

@admin.register(ReplenishmentRecommendation)
class ReplenishmentWorkflowAdmin(BaseInventoryAdmin):
    """Specialized admin for replenishment workflow."""
    
    list_display = [
        'product_info', 'warehouse', 'stock_status', 'priority_display',
        'replenishment_details', 'supplier_info', 'cost_analysis',
        'timeline', 'action_buttons'
    ]
    
    list_filter = [
        'priority', 'status', 'warehouse',
        ('created_at', admin.DateFieldListFilter),
        'recommended_supplier'
    ]
    
    search_fields = [
        'product__name', 'product__sku', 'warehouse__name',
        'recommended_supplier__name'
    ]
    
    fieldsets = (
        ('Product & Location', {
            'fields': (
                'product', 'warehouse', 'recommended_supplier'
            )
        }),
        ('Stock Analysis', {
            'fields': (
                'current_stock', 'reorder_level', 'max_stock_level',
                'recommended_quantity'
            )
        }),
        ('Planning', {
            'fields': (
                'priority', 'status', 'estimated_cost', 'lead_time_days'
            )
        }),
        ('Demand Forecast', {
            'fields': ('demand_forecast',),
            'classes': ('collapse',)
        })
    )
    
    actions = [
        'approve_replenishment', 'create_purchase_orders', 'reject_recommendations',
        'update_priorities', 'recalculate_recommendations', 'export_replenishment_plan'
    ]
    
    def get_urls(self):
        """Add replenishment workflow URLs."""
        urls = super().get_urls()
        custom_urls = [
            path(
                'dashboard/',
                self.admin_site.admin_view(self.replenishment_dashboard),
                name='replenishment-dashboard'
            ),
            path(
                'generate-recommendations/',
                self.admin_site.admin_view(self.generate_recommendations),
                name='generate-recommendations'
            ),
            path(
                'optimization-analysis/',
                self.admin_site.admin_view(self.optimization_analysis),
                name='replenishment-optimization'
            ),
            path(
                '<int:recommendation_id>/create-po/',
                self.admin_site.admin_view(self.create_purchase_order),
                name='create-po-from-recommendation'
            ),
        ]
        return custom_urls + urls
    
    def product_info(self, obj):
        """Display product information with stock levels."""
        product_url = reverse('admin:inventory_product_change', args=[obj.product.id])
        
        return format_html(
            '<a href="{}" title="{}">{}</a><br/>'
            '<small>SKU: {} | ABC: {}</small>',
            product_url, obj.product.description or '',
            obj.product.name, obj.product.sku,
            obj.product.abc_classification or 'N/A'
        )
    product_info.short_description = 'Product'
    
    def stock_status(self, obj):
        """Show current stock status with visual indicators."""
        stock_percentage = (obj.current_stock / obj.max_stock_level * 100) if obj.max_stock_level > 0 else 0
        reorder_percentage = (obj.current_stock / obj.reorder_level * 100) if obj.reorder_level > 0 else 0
        
        if obj.current_stock == 0:
            color = 'red'
            status = 'OUT OF STOCK'
            icon = '🔴'
        elif reorder_percentage <= 100:
            color = 'orange'
            status = 'BELOW REORDER'
            icon = '🟠'
        elif stock_percentage >= 90:
            color = 'blue'
            status = 'HIGH STOCK'
            icon = '🔵'
        else:
            color = 'green'
            status = 'NORMAL'
            icon = '🟢'
        
        return format_html(
            '<div>'
            '<span style="color: {}; font-weight: bold;">{} {}</span><br/>'
            'Current: <strong>{}</strong><br/>'
            'Reorder: {} | Max: {}'
            '</div>',
            color, icon, status,
            int(obj.current_stock),
            int(obj.reorder_level), int(obj.max_stock_level)
        )
    stock_status.short_description = 'Stock Status'
    
    def priority_display(self, obj):
        """Show priority with visual indicators."""
        priority_colors = {
            'CRITICAL': 'red',
            'HIGH': 'orange',
            'MEDIUM': 'blue',
            'LOW': 'green'
        }
        
        priority_icons = {
            'CRITICAL': '🚨',
            'HIGH': '⚠️',
            'MEDIUM': '📋',
            'LOW': '📝'
        }
        
        color = priority_colors.get(obj.priority, 'black')
        icon = priority_icons.get(obj.priority, '📋')
        
        return format_html(
            '<span style="color: {}; font-weight: bold; font-size: 1.1em;">{} {}</span>',
            color, icon, obj.get_priority_display()
        )
    priority_display.short_description = 'Priority'
    
    def replenishment_details(self, obj):
        """Show replenishment calculation details."""
        # Calculate shortage
        shortage = max(0, obj.reorder_level - obj.current_stock)
        
        # Calculate optimal order quantity (considering EOQ if available)
        safety_stock = obj.max_stock_level - obj.reorder_level
        
        return format_html(
            '<div>'
            '<strong>Recommended: {}</strong><br/>'
            'Shortage: <span style="color: red;">{}</span><br/>'
            'Safety Stock: {}<br/>'
            'Order Point: {}'
            '</div>',
            int(obj.recommended_quantity),
            int(shortage),
            int(safety_stock),
            int(obj.reorder_level)
        )
    replenishment_details.short_description = 'Replenishment'
    
    def supplier_info(self, obj):
        """Show supplier information."""
        if obj.recommended_supplier:
            supplier_url = reverse('admin:inventory_supplier_change', args=[obj.recommended_supplier.id])
            
            return format_html(
                '<a href="{}">{}</a><br/>'
                '<small>Lead Time: {} days</small>',
                supplier_url, obj.recommended_supplier.name,
                obj.lead_time_days
            )
        
        return format_html(
            '<span style="color: red;">No Supplier</span>'
        )
    supplier_info.short_description = 'Supplier'
    
    def cost_analysis(self, obj):
        """Show cost analysis."""
        unit_cost = obj.estimated_cost / obj.recommended_quantity if obj.recommended_quantity > 0 else 0
        
        # Calculate inventory carrying cost impact
        carrying_cost_rate = 0.25  # 25% annual carrying cost
        annual_carrying_cost = obj.estimated_cost * carrying_cost_rate
        
        return format_html(
            '<div>'
            'Total: <strong>${:,.2f}</strong><br/>'
            'Unit: ${:.2f}<br/>'
            'Annual Carrying: ${:,.2f}'
            '</div>',
            obj.estimated_cost, unit_cost, annual_carrying_cost
        )
    cost_analysis.short_description = 'Cost Analysis'
    
    def timeline(self, obj):
        """Show timeline and urgency."""
        days_since_created = (timezone.now() - obj.created_at).days
        
        # Calculate stockout risk timeline
        if obj.current_stock <= 0:
            urgency = "IMMEDIATE"
            color = "red"
        elif obj.lead_time_days > 0:
            # Estimate days until stockout based on demand
            avg_daily_demand = 1  # This would come from demand_forecast
            days_until_stockout = obj.current_stock / avg_daily_demand if avg_daily_demand > 0 else float('inf')
            
            if days_until_stockout <= obj.lead_time_days:
                urgency = f"URGENT ({int(days_until_stockout)}d)"
                color = "red"
            elif days_until_stockout <= obj.lead_time_days * 1.5:
                urgency = f"SOON ({int(days_until_stockout)}d)"
                color = "orange"
            else:
                urgency = f"PLANNED ({int(days_until_stockout)}d)"
                color = "green"
        else:
            urgency = "UNKNOWN"
            color = "gray"
        
        return format_html(
            '<div>'
            '<span style="color: {}; font-weight: bold;">{}</span><br/>'
            '<small>Lead Time: {}d</small><br/>'
            '<small>Created: {}d ago</small>'
            '</div>',
            color, urgency, obj.lead_time_days, days_since_created
        )
    timeline.short_description = 'Timeline'
    
    def action_buttons(self, obj):
        """Show action buttons."""
        buttons = []
        
        if obj.status == 'PENDING':
            buttons.append(
                f'<a href="/admin/inventory/replenishmentrecommendation/{obj.id}/create-po/" '
                f'class="button" style="font-size: 0.8em; padding: 2px 6px;">Create PO</a>'
            )
        
        if obj.status == 'APPROVED':
            buttons.append(
                '<span style="color: green; font-size: 0.8em;">✓ Approved</span>'
            )
        elif obj.status == 'ORDERED':
            buttons.append(
                '<span style="color: blue; font-size: 0.8em;">📦 Ordered</span>'
            )
        elif obj.status == 'REJECTED':
            buttons.append(
                '<span style="color: red; font-size: 0.8em;">❌ Rejected</span>'
            )
        
        return format_html('<br/>'.join(buttons)) if buttons else '-'
    action_buttons.short_description = 'Actions'
    
    def approve_replenishment(self, request, queryset):
        """Approve selected replenishment recommendations."""
        approved = queryset.filter(status='PENDING').update(
            status='APPROVED',
            updated_at=timezone.now()
        )
        
        self.message_user(
            request,
            f'{approved} replenishment recommendations approved.',
            messages.SUCCESS
        )
    approve_replenishment.short_description = "Approve replenishment"
    
    def create_purchase_orders(self, request, queryset):
        """Create purchase orders from approved recommendations."""
        created_pos = 0
        
        # Group recommendations by supplier
        supplier_recommendations = {}
        for recommendation in queryset.filter(status='APPROVED'):
            supplier = recommendation.recommended_supplier
            if supplier:
                if supplier not in supplier_recommendations:
                    supplier_recommendations[supplier] = []
                supplier_recommendations[supplier].append(recommendation)
        
        for supplier, recommendations in supplier_recommendations.items():
            # Create PO for this supplier
            po = PurchaseOrder.objects.create(
                tenant=request.user.tenant,
                po_number=f"PO-REP-{timezone.now().strftime('%Y%m%d')}-{supplier.id}",
                supplier=supplier,
                warehouse=recommendations[0].warehouse,  # Use first warehouse
                order_date=timezone.now().date(),
                status='DRAFT',
                created_by=request.user
            )
            
            total_amount = 0
            
            for recommendation in recommendations:
                # Create PO item
                po_item = po.items.create(
                    product=recommendation.product,
                    quantity_ordered=recommendation.recommended_quantity,
                    unit_cost=recommendation.estimated_cost / recommendation.recommended_quantity,
                    total_cost=recommendation.estimated_cost
                )
                
                total_amount += recommendation.estimated_cost
                
                # Update recommendation status
                recommendation.status = 'ORDERED'
                recommendation.save()
            
            po.total_amount = total_amount
            po.save()
            
            created_pos += 1
        
        self.message_user(
            request,
            f'{created_pos} purchase orders created from replenishment recommendations.',
            messages.SUCCESS
        )
    create_purchase_orders.short_description = "Create purchase orders"
    
    def generate_recommendations(self, request):
        """Generate new replenishment recommendations."""
        reorder_service = ReorderService()
        
        # Get products below reorder level
        low_stock_items = StockItem.objects.filter(
            tenant=request.user.tenant,
            quantity_on_hand__lte=F('product__reorder_level')
        ).select_related('product', 'warehouse')
        
        recommendations_created = 0
        
        for stock_item in low_stock_items:
            # Check if recommendation already exists
            existing = ReplenishmentRecommendation.objects.filter(
                tenant=request.user.tenant,
                product=stock_item.product,
                warehouse=stock_item.warehouse,
                status__in=['PENDING', 'APPROVED']
            ).exists()
            
            if not existing:
                # Calculate recommendation
                recommendation_data = reorder_service.calculate_reorder_recommendation(
                    stock_item.product, stock_item.warehouse
                )
                
                ReplenishmentRecommendation.objects.create(
                    tenant=request.user.tenant,
                    product=stock_item.product,
                    warehouse=stock_item.warehouse,
                    current_stock=stock_item.quantity_on_hand,
                    reorder_level=stock_item.product.reorder_level,
                    max_stock_level=stock_item.product.max_stock_level,
                    recommended_quantity=recommendation_data['quantity'],
                    recommended_supplier=recommendation_data['supplier'],
                    priority=recommendation_data['priority'],
                    estimated_cost=recommendation_data['cost'],
                    lead_time_days=recommendation_data['lead_time'],
                    demand_forecast=recommendation_data['forecast'],
                    created_by=request.user
                )
                
                recommendations_created += 1
        
        return JsonResponse({
            'success': True,
            'recommendations_created': recommendations_created,
            'message': f'{recommendations_created} new replenishment recommendations generated.'
        })