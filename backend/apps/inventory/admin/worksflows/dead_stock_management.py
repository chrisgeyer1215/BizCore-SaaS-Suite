# apps/inventory/admin/workflows/dead_stock_management.py

from django.contrib import admin
from django.utils.html import format_html
from django.db.models import Count, Sum, F, Q, Avg, Max, Min
from django.urls import reverse, path
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.contrib import messages
from django.utils import timezone
from datetime import timedelta

from ..base import BaseInventoryAdmin, InlineAdminMixin

class DeadStockAnalysis(models.Model):
    """Model for dead stock analysis runs."""
    tenant = models.ForeignKey('core.Tenant', on_delete=models.CASCADE)
    analysis_name = models.CharField(max_length=200)
    
    # Analysis criteria
    no_movement_days = models.IntegerField(default=365)  # No movement for X days
    low_turnover_threshold = models.DecimalField(max_digits=5, decimal_places=2, default=0.5)  # Turns per year
    obsolescence_indicators = models.JSONField(default=dict)  # Custom indicators
    
    # Filters
    warehouse_filter = models.ManyToManyField('inventory.Warehouse', blank=True)
    category_filter = models.ManyToManyField('inventory.Category', blank=True)
    min_inventory_value = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    
    # Analysis period
    analysis_date = models.DateField(default=timezone.now)
    
    # Status
    status = models.CharField(
        max_length=20,
        choices=[
            ('DRAFT', 'Draft'),
            ('RUNNING', 'Running'),
            ('COMPLETED', 'Completed'),
            ('FAILED', 'Failed'),
            ('ARCHIVED', 'Archived')
        ],
        default='DRAFT'
    )
    
    # Results summary
    total_products_analyzed = models.IntegerField(default=0)
    dead_stock_items = models.IntegerField(default=0)
    slow_moving_items = models.IntegerField(default=0)
    obsolete_items = models.IntegerField(default=0)
    
    total_dead_stock_value = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    potential_write_off_value = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True)

class DeadStockItem(models.Model):
    """Individual dead stock items identified in analysis."""
    analysis = models.ForeignKey(DeadStockAnalysis, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey('inventory.Product', on_delete=models.CASCADE)
    warehouse = models.ForeignKey('inventory.Warehouse', on_delete=models.CASCADE)
    
    # Stock information
    current_quantity = models.DecimalField(max_digits=15, decimal_places=4)
    unit_cost = models.DecimalField(max_digits=15, decimal_places=2)
    total_value = models.DecimalField(max_digits=15, decimal_places=2)
    
    # Movement analysis
    days_since_last_movement = models.IntegerField()
    last_movement_date = models.DateField(null=True, blank=True)
    last_movement_type = models.CharField(max_length=30, blank=True)
    annual_turnover = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    
    # Classification
    dead_stock_category = models.CharField(
        max_length=30,
        choices=[
            ('DEAD', 'Dead Stock'),
            ('SLOW_MOVING', 'Slow Moving'),
            ('OBSOLETE', 'Obsolete'),
            ('EXCESS', 'Excess Inventory'),
            ('DAMAGED', 'Damaged/Unsaleable')
        ]
    )
    
    risk_level = models.CharField(
        max_length=20,
        choices=[
            ('LOW', 'Low'),
            ('MEDIUM', 'Medium'),
            ('HIGH', 'High'),
            ('CRITICAL', 'Critical')
        ]
    )
    
    # Disposition recommendations
    recommended_action = models.CharField(
        max_length=30,
        choices=[
            ('LIQUIDATE', 'Liquidate'),
            ('DISCOUNT_SALE', 'Discount Sale'),
            ('RETURN_TO_SUPPLIER', 'Return to Supplier'),
            ('DONATE', 'Donate'),
            ('RECYCLE', 'Recycle/Scrap'),
            ('REWORK', 'Rework'),
            ('TRANSFER', 'Transfer Location'),
            ('WRITE_OFF', 'Write Off'),
            ('MONITOR', 'Continue Monitoring')
        ]
    )
    
    # Financial impact
    estimated_recovery_value = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    carrying_cost_saved = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    
    # Action tracking
    action_taken = models.CharField(max_length=30, blank=True)
    action_date = models.DateField(null=True, blank=True)
    action_notes = models.TextField(blank=True)
    disposal_approved = models.BooleanField(default=False)
    
    # Additional analysis data
    supplier_info = models.JSONField(default=dict)
    demand_history = models.JSONField(default=dict)
    aging_analysis = models.JSONField(default=dict)

class DeadStockItemInline(admin.TabularInline):
    """Inline for dead stock items."""
    model = DeadStockItem
    fields = [
        'product', 'warehouse', 'current_quantity', 'total_value',
        'dead_stock_category', 'recommended_action', 'disposal_approved'
    ]
    readonly_fields = ['total_value']
    extra = 0
    max_num = 20
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('product', 'warehouse').order_by('-total_value')

@admin.register(DeadStockAnalysis)
class DeadStockManagementWorkflowAdmin(BaseInventoryAdmin):
    """Specialized admin for dead stock management workflow."""
    
    list_display = [
        'analysis_name', 'analysis_date', 'status_display',
        'dead_stock_summary', 'financial_impact', 'action_progress',
        'disposal_timeline', 'risk_assessment'
    ]
    
    list_filter = [
        'status',
        ('analysis_date', admin.DateFieldListFilter),
        ('created_at', admin.DateFieldListFilter)
    ]
    
    search_fields = [
        'analysis_name', 'created_by__username'
    ]
    
    inlines = [DeadStockItemInline]
    
    fieldsets = (
        ('Analysis Configuration', {
            'fields': (
                'analysis_name', 'analysis_date',
                'no_movement_days', 'low_turnover_threshold'
            )
        }),
        ('Filters', {
            'fields': (
                'warehouse_filter', 'category_filter', 'min_inventory_value'
            )
        }),
        ('Results Summary', {
            'fields': (
                'total_products_analyzed', 'dead_stock_items', 'slow_moving_items',
                'obsolete_items', 'total_dead_stock_value', 'potential_write_off_value'
            ),
            'classes': ('collapse',)
        }),
        ('Status', {
            'fields': ('status',)
        })
    )
    
    readonly_fields = [
        'total_products_analyzed', 'dead_stock_items', 'slow_moving_items',
        'obsolete_items', 'total_dead_stock_value', 'potential_write_off_value'
    ] + BaseInventoryAdmin.readonly_fields
    
    actions = [
        'run_dead_stock_analysis', 'approve_disposals', 'create_liquidation_orders',
        'generate_write_off_journal', 'export_dead_stock_report'
    ]
    
    def get_urls(self):
        """Add dead stock management URLs."""
        urls = super().get_urls()
        custom_urls = [
            path(
                'dead-stock-dashboard/',
                self.admin_site.admin_view(self.dead_stock_dashboard),
                name='dead-stock-dashboard'
            ),
            path(
                '<int:analysis_id>/run/',
                self.admin_site.admin_view(self.run_analysis),
                name='run-dead-stock-analysis'
            ),
            path(
                '<int:analysis_id>/aging-report/',
                self.admin_site.admin_view(self.aging_report),
                name='dead-stock-aging-report'
            ),
            path(
                'liquidation-planning/',
                self.admin_site.admin_view(self.liquidation_planning),
                name='liquidation-planning'
            ),
        ]
        return custom_urls + urls
    
    def status_display(self, obj):
        """Show status with timing."""
        status_colors = {
            'DRAFT': 'gray',
            'RUNNING': 'blue',
            'COMPLETED': 'green',
            'FAILED': 'red',
            'ARCHIVED': 'purple'
        }
        
        color = status_colors.get(obj.status, 'black')
        
        return format_html(
            '<span style="color: {}; font-weight: bold;">● {}</span>',
            color, obj.get_status_display()
        )
    status_display.short_description = 'Status'
    
    def dead_stock_summary(self, obj):
        """Show dead stock summary."""
        if obj.status != 'COMPLETED':
            return 'Analysis not completed'
        
        total_items = obj.dead_stock_items + obj.slow_moving_items + obj.obsolete_items
        
        return format_html(
            '<div style="font-size: 0.9em;">'
            'Total Issues: <strong>{}</strong><br/>'
            'Dead: <span style="color: red;">{}</span><br/>'
            'Slow: <span style="color: orange;">{}</span><br/>'
            'Obsolete: <span style="color: purple;">{}</span>'
            '</div>',
            total_items, obj.dead_stock_items, obj.slow_moving_items, obj.obsolete_items
        )
    dead_stock_summary.short_description = 'Summary'
    
    def financial_impact(self, obj):
        """Show financial impact."""
        if obj.total_dead_stock_value <= 0:
            return 'No impact'
        
        # Calculate potential recovery vs write-off
        recovery_rate = (obj.total_dead_stock_value - obj.potential_write_off_value) / obj.total_dead_stock_value * 100 if obj.total_dead_stock_value > 0 else 0
        
        return format_html(
            '<div>'
            'Dead Stock Value: <strong>${:,.0f}</strong><br/>'
            'Potential Write-off: <span style="color: red;">${:,.0f}</span><br/>'
            'Recovery Rate: <span style="color: {};">{:.1f}%</span>'
            '</div>',
            obj.total_dead_stock_value, obj.potential_write_off_value,
            'green' if recovery_rate > 50 else 'orange' if recovery_rate > 25 else 'red',
            recovery_rate
        )
    financial_impact.short_description = 'Financial Impact'
    
    def action_progress(self, obj):
        """Show action progress."""
        if obj.status != 'COMPLETED':
            return 'N/A'
        
        total_items = obj.items.count()
        if total_items == 0:
            return 'No items'
        
        approved_items = obj.items.filter(disposal_approved=True).count()
        actioned_items = obj.items.exclude(action_taken='').count()
        
        approval_rate = (approved_items / total_items * 100)
        action_rate = (actioned_items / total_items * 100)
        
        return format_html(
            '<div>'
            'Approved: <span style="color: blue;">{:.1f}%</span><br/>'
            'Actioned: <span style="color: green;">{:.1f}%</span><br/>'
            '<small>{}/{} items</small>'
            '</div>',
            approval_rate, action_rate, actioned_items, total_items
        )
    action_progress.short_description = 'Actions'
    
    def disposal_timeline(self, obj):
        """Show disposal timeline and urgency."""
        if obj.status != 'COMPLETED':
            return 'N/A'
        
        # Calculate average age of dead stock
        items = obj.items.all()
        if not items:
            return 'No items'
        
        avg_age = sum(item.days_since_last_movement for item in items) / len(items)
        
        # Determine urgency based on age and value
        high_value_old = obj.items.filter(
            days_since_last_movement__gte=730,  # 2+ years
            total_value__gte=1000
        ).count()
        
        if avg_age > 730:  # 2+ years
            urgency = 'CRITICAL'
            color = 'red'
            icon = '🚨'
        elif avg_age > 365:  # 1+ year
            urgency = 'HIGH'
            color = 'orange'
            icon = '⚠️'
        else:
            urgency = 'MEDIUM'
            color = 'blue'
            icon = '📅'
        
        return format_html(
            '<div style="text-align: center;">'
            '<span style="font-size: 1.2em;">{}</span><br/>'
            '<span style="color: {}; font-weight: bold;">{}</span><br/>'
            '<small>Avg Age: {:.0f} days</small><br/>'
            '<small>High Value: {}</small>'
            '</div>',
            icon, color, urgency, avg_age, high_value_old
        )
    disposal_timeline.short_description = 'Timeline'
    
    def risk_assessment(self, obj):
        """Show risk assessment."""
        if obj.status != 'COMPLETED':
            return 'N/A'
        
        # Risk factors
        total_value = obj.total_dead_stock_value
        items_count = obj.items.count()
        
        risk_factors = []
        
        if total_value > 100000:  # High value threshold
            risk_factors.append("High Value")
        
        if items_count > 100:  # Large quantity
            risk_factors.append("Large Quantity")
        
        # Check for perishable or hazardous items
        hazardous_items = obj.items.filter(
            product__storage_requirements__icontains='hazmat'
        ).count()
        
        if hazardous_items > 0:
            risk_factors.append("Hazardous Materials")
        
        # Storage cost impact
        if total_value > 50000:
            risk_factors.append("Storage Cost Impact")
        
        if not risk_factors:
            return format_html(
                '<span style="color: green;">✅ Low Risk</span>'
            )
        elif len(risk_factors) <= 2:
            return format_html(
                '<span style="color: orange;">⚠️ Medium Risk</span><br/>'
                '<small>{}</small>',
                ', '.join(risk_factors)
            )
        else:
            return format_html(
                '<span style="color: red;">🚨 High Risk</span><br/>'
                '<small>{} factors</small>',
                len(risk_factors)
            )
    risk_assessment.short_description = 'Risk Assessment'
    
    def run_dead_stock_analysis(self, request, queryset):
        """Run dead stock analysis."""
        from ...services.analytics.dead_stock_analyzer import DeadStockAnalyzer
        
        completed = 0
        for analysis in queryset.filter(status='DRAFT'):
            analysis.status = 'RUNNING'
            analysis.save()
            
            try:
                analyzer = DeadStockAnalyzer()
                results = analyzer.analyze_dead_stock(analysis)
                
                analysis.status = 'COMPLETED'
                analysis.save()
                completed += 1
                
            except Exception as e:
                analysis.status = 'FAILED'
                analysis.save()
        
        self.message_user(
            request,
            f'{completed} dead stock analyses completed.',
            messages.SUCCESS
        )
    run_dead_stock_analysis.short_description = "Run dead stock analysis"
    
    def approve_disposals(self, request, queryset):
        """Approve disposal recommendations."""
        approved_count = 0
        
        for analysis in queryset.filter(status='COMPLETED'):
            # Auto-approve low-value items or items meeting criteria
            auto_approve_items = analysis.items.filter(
                Q(total_value__lt=100) |  # Low value items
                Q(days_since_last_movement__gte=730),  # Very old items
                disposal_approved=False
            )
            
            approved_count += auto_approve_items.update(disposal_approved=True)
        
        self.message_user(
            request,
            f'{approved_count} disposal items approved.',
            messages.SUCCESS
        )
    approve_disposals.short_description = "Approve disposals"
    
    def dead_stock_dashboard(self, request):
        """Generate dead stock dashboard data."""
        # Get summary statistics across all analyses
        recent_analyses = DeadStockAnalysis.objects.filter(
            tenant=request.user.tenant,
            status='COMPLETED',
            analysis_date__gte=timezone.now().date() - timedelta(days=90)
        )
        
        dashboard_data = {
            'total_dead_stock_value': recent_analyses.aggregate(
                total=Sum('total_dead_stock_value')
            )['total'] or 0,
            'items_by_category': list(
                DeadStockItem.objects.filter(
                    analysis__in=recent_analyses
                ).values('dead_stock_category').annotate(
                    count=Count('id'),
                    total_value=Sum('total_value')
                )
            ),
            'top_dead_stock_products': list(
                DeadStockItem.objects.filter(
                    analysis__in=recent_analyses
                ).values(
                    'product__name', 'product__sku'
                ).annotate(
                    total_value=Sum('total_value'),
                    total_quantity=Sum('current_quantity')
                ).order_by('-total_value')[:10]
            ),
            'disposal_progress': {
                'approved': DeadStockItem.objects.filter(
                    analysis__in=recent_analyses,
                    disposal_approved=True
                ).count(),
                'actioned': DeadStockItem.objects.filter(
                    analysis__in=recent_analyses
                ).exclude(action_taken='').count()
            }
        }
        
        return JsonResponse(dashboard_data)