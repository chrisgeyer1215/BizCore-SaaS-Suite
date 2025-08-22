# apps/inventory/admin/workflows/quality_control.py

from django.contrib import admin
from django.utils.html import format_html
from django.db.models import Count, Sum, F, Q, Avg
from django.urls import reverse, path
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.contrib import messages
from django.utils import timezone

from ..base import BaseInventoryAdmin, InlineAdminMixin

class QualityInspection(models.Model):
    """Model for quality inspections."""
    tenant = models.ForeignKey('core.Tenant', on_delete=models.CASCADE)
    inspection_number = models.CharField(max_length=50, unique=True)
    
    # What's being inspected
    stock_receipt = models.ForeignKey('inventory.StockReceipt', on_delete=models.CASCADE, null=True, blank=True)
    batch = models.ForeignKey('inventory.Batch', on_delete=models.CASCADE, null=True, blank=True)
    product = models.ForeignKey('inventory.Product', on_delete=models.CASCADE)
    supplier = models.ForeignKey('inventory.Supplier', on_delete=models.CASCADE)
    
    # Inspection details
    inspection_type = models.CharField(
        max_length=30,
        choices=[
            ('INCOMING', 'Incoming Inspection'),
            ('IN_PROCESS', 'In-Process Inspection'),
            ('FINAL', 'Final Inspection'),
            ('SUPPLIER_AUDIT', 'Supplier Audit'),
            ('CUSTOMER_COMPLAINT', 'Customer Complaint'),
            ('RANDOM_SAMPLING', 'Random Sampling')
        ]
    )
    
    quantity_inspected = models.DecimalField(max_digits=15, decimal_places=4)
    quantity_total = models.DecimalField(max_digits=15, decimal_places=4)
    
    # Results
    status = models.CharField(
        max_length=20,
        choices=[
            ('PENDING', 'Pending'),
            ('IN_PROGRESS', 'In Progress'),
            ('PASSED', 'Passed'),
            ('FAILED', 'Failed'),
            ('CONDITIONAL_PASS', 'Conditional Pass'),
            ('REJECTED', 'Rejected')
        ],
        default='PENDING'
    )
    
    overall_score = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    defect_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    
    # Disposition
    disposition = models.CharField(
        max_length=30,
        choices=[
            ('ACCEPT', 'Accept'),
            ('REWORK', 'Rework'),
            ('RETURN_TO_SUPPLIER', 'Return to Supplier'),
            ('QUARANTINE', 'Quarantine'),
            ('SCRAP', 'Scrap'),
            ('USE_AS_IS', 'Use As-Is')
        ],
        null=True, blank=True
    )
    
    # Inspector information
    inspector = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True, related_name='inspections')
    inspection_date = models.DateTimeField()
    completion_date = models.DateTimeField(null=True, blank=True)
    
    # Documentation
    inspection_notes = models.TextField(blank=True)
    corrective_actions = models.TextField(blank=True)
    photos_path = models.CharField(max_length=500, blank=True)
    
    # Approval
    approved_by = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True, related_name='approved_inspections')
    approved_at = models.DateTimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

class QualityCheckpoint(models.Model):
    """Individual quality checkpoints within an inspection."""
    inspection = models.ForeignKey(QualityInspection, on_delete=models.CASCADE, related_name='checkpoints')
    
    checkpoint_name = models.CharField(max_length=200)
    specification = models.TextField()
    measurement_type = models.CharField(
        max_length=20,
        choices=[
            ('VISUAL', 'Visual'),
            ('DIMENSIONAL', 'Dimensional'),
            ('FUNCTIONAL', 'Functional'),
            ('MATERIAL', 'Material'),
            ('DOCUMENTATION', 'Documentation')
        ]
    )
    
    expected_value = models.CharField(max_length=100, blank=True)
    actual_value = models.CharField(max_length=100, blank=True)
    tolerance = models.CharField(max_length=50, blank=True)
    
    result = models.CharField(
        max_length=20,
        choices=[
            ('PASS', 'Pass'),
            ('FAIL', 'Fail'),
            ('WARNING', 'Warning'),
            ('NOT_TESTED', 'Not Tested')
        ],
        default='NOT_TESTED'
    )
    
    severity = models.CharField(
        max_length=20,
        choices=[
            ('CRITICAL', 'Critical'),
            ('MAJOR', 'Major'),
            ('MINOR', 'Minor'),
            ('COSMETIC', 'Cosmetic')
        ],
        default='MINOR'
    )
    
    notes = models.TextField(blank=True)

class QualityCheckpointInline(InlineAdminMixin, admin.TabularInline):
    """Inline for quality checkpoints."""
    model = QualityCheckpoint
    fields = [
        'checkpoint_name', 'measurement_type', 'expected_value',
        'actual_value', 'result', 'severity', 'notes'
    ]
    extra = 5

@admin.register(QualityInspection)
class QualityControlWorkflowAdmin(BaseInventoryAdmin):
    """Specialized admin for quality control workflow."""
    
    list_display = [
        'inspection_number', 'inspection_type', 'product_info',
        'supplier', 'quantity_info', 'status_display',
        'quality_score', 'inspector_info', 'disposition_display',
        'timeline_info'
    ]
    
    list_filter = [
        'inspection_type', 'status', 'disposition',
        'supplier', 'inspector',
        ('inspection_date', admin.DateFieldListFilter),
        ('completion_date', admin.DateFieldListFilter)
    ]
    
    search_fields = [
        'inspection_number', 'product__name', 'product__sku',
        'supplier__name', 'inspector__username'
    ]
    
    inlines = [QualityCheckpointInline]
    
    fieldsets = (
        ('Inspection Information', {
            'fields': (
                'inspection_number', 'inspection_type', 'product',
                'supplier', 'stock_receipt', 'batch'
            )
        }),
        ('Quantities', {
            'fields': (
                'quantity_inspected', 'quantity_total'
            )
        }),
        ('Results', {
            'fields': (
                'status', 'overall_score', 'defect_rate', 'disposition'
            )
        }),
        ('Inspector & Timeline', {
            'fields': (
                'inspector', 'inspection_date', 'completion_date'
            )
        }),
        ('Documentation', {
            'fields': (
                'inspection_notes', 'corrective_actions', 'photos_path'
            )
        }),
        ('Approval', {
            'fields': (
                'approved_by', 'approved_at'
            )
        })
    )
    
    readonly_fields = ['approved_by', 'approved_at'] + BaseInventoryAdmin.readonly_fields
    
    actions = [
        'approve_inspections', 'reject_inspections', 'schedule_re_inspection',
        'create_supplier_feedback', 'generate_quality_report'
    ]
    
    def get_urls(self):
        """Add quality control URLs."""
        urls = super().get_urls()
        custom_urls = [
            path(
                'quality-dashboard/',
                self.admin_site.admin_view(self.quality_dashboard),
                name='quality-dashboard'
            ),
            path(
                '<int:inspection_id>/photos/',
                self.admin_site.admin_view(self.inspection_photos),
                name='inspection-photos'
            ),
            path(
                'supplier-quality-report/',
                self.admin_site.admin_view(self.supplier_quality_report),
                name='supplier-quality-report'
            ),
        ]
        return custom_urls + urls
    
    def product_info(self, obj):
        """Display product information."""
        product_url = reverse('admin:inventory_product_change', args=[obj.product.id])
        
        return format_html(
            '<a href="{}">{}</a><br/>'
            '<small>SKU: {}</small>',
            product_url, obj.product.name, obj.product.sku
        )
    product_info.short_description = 'Product'
    
    def quantity_info(self, obj):
        """Show quantity information."""
        inspection_percentage = (obj.quantity_inspected / obj.quantity_total * 100) if obj.quantity_total > 0 else 0
        
        return format_html(
            '<div>'
            'Inspected: <strong>{}</strong><br/>'
            'Total: {}<br/>'
            'Coverage: <small>{:.1f}%</small>'
            '</div>',
            int(obj.quantity_inspected),
            int(obj.quantity_total),
            inspection_percentage
        )
    quantity_info.short_description = 'Quantities'
    
    def status_display(self, obj):
        """Show status with color coding."""
        status_colors = {
            'PENDING': 'gray',
            'IN_PROGRESS': 'blue',
            'PASSED': 'green',
            'FAILED': 'red',
            'CONDITIONAL_PASS': 'orange',
            'REJECTED': 'darkred'
        }
        
        color = status_colors.get(obj.status, 'black')
        
        return format_html(
            '<span style="color: {}; font-weight: bold;">● {}</span>',
            color, obj.get_status_display()
        )
    status_display.short_description = 'Status'
    
    def quality_score(self, obj):
        """Show quality score with defect rate."""
        if obj.overall_score is not None:
            # Color code score
            if obj.overall_score >= 95:
                color = 'green'
            elif obj.overall_score >= 85:
                color = 'blue'
            elif obj.overall_score >= 75:
                color = 'orange'
            else:
                color = 'red'
            
            return format_html(
                '<div>'
                'Score: <span style="color: {}; font-weight: bold;">{:.1f}%</span><br/>'
                'Defects: <span style="color: red;">{:.2f}%</span>'
                '</div>',
                color, obj.overall_score, obj.defect_rate
            )
        
        return 'Not scored'
    quality_score.short_description = 'Quality Score'
    
    def inspector_info(self, obj):
        """Show inspector information."""
        if obj.inspector:
            return format_html(
                '{}<br/>'
                '<small>{}</small>',
                obj.inspector.get_full_name(),
                obj.inspection_date.strftime('%m/%d/%Y')
            )
        return 'Not assigned'
    inspector_info.short_description = 'Inspector'
    
    def disposition_display(self, obj):
        """Show disposition with color coding."""
        if not obj.disposition:
            return 'Pending'
        
        disposition_colors = {
            'ACCEPT': 'green',
            'REWORK': 'blue',
            'RETURN_TO_SUPPLIER': 'orange',
            'QUARANTINE': 'red',
            'SCRAP': 'darkred',
            'USE_AS_IS': 'purple'
        }
        
        color = disposition_colors.get(obj.disposition, 'black')
        
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color, obj.get_disposition_display()
        )
    disposition_display.short_description = 'Disposition'
    
    def timeline_info(self, obj):
        """Show timeline information."""
        if obj.completion_date:
            duration = obj.completion_date - obj.inspection_date
            duration_hours = duration.total_seconds() / 3600
            
            return format_html(
                '<div>'
                'Started: {}<br/>'
                'Completed: {}<br/>'
                'Duration: <strong>{:.1f}h</strong>'
                '</div>',
                obj.inspection_date.strftime('%m/%d %H:%M'),
                obj.completion_date.strftime('%m/%d %H:%M'),
                duration_hours
            )
        else:
            duration = timezone.now() - obj.inspection_date
            duration_hours = duration.total_seconds() / 3600
            
            return format_html(
                '<div>'
                'Started: {}<br/>'
                'In Progress: <span style="color: blue;">{:.1f}h</span>'
                '</div>',
                obj.inspection_date.strftime('%m/%d %H:%M'),
                duration_hours
            )
    timeline_info.short_description = 'Timeline'