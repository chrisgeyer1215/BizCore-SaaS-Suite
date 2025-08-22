# apps/inventory/admin/workflows/purchase_approval.py

from django.contrib import admin
from django.utils.html import format_html
from django.db.models import Count, Sum, F, Q
from django.urls import reverse, path
from django.http import JsonResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.contrib import messages
from django.utils import timezone
from django.core.mail import send_mail
from django.template.loader import render_to_string

from ..base import BaseInventoryAdmin, InlineAdminMixin
from ...models.purchasing import PurchaseOrder, PurchaseOrderApproval
from ...utils.choices import PO_STATUS_CHOICES

class PurchaseOrderApprovalInline(InlineAdminMixin, admin.TabularInline):
    """Inline for PO approvals."""
    model = PurchaseOrderApproval
    fields = [
        'approver', 'approval_level', 'status', 'approved_amount',
        'comments', 'approved_at'
    ]
    readonly_fields = ['approved_at']
    extra = 0
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('approver').order_by('approval_level')

@admin.register(PurchaseOrder)
class PurchaseOrderApprovalWorkflowAdmin(BaseInventoryAdmin):
    """Specialized admin for PO approval workflow."""
    
    # Override the model registration to avoid conflicts
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # This would be registered with a different name to avoid conflicts
        
    list_display = [
        'po_number', 'supplier', 'total_amount', 'approval_status_display',
        'current_approval_level', 'approval_progress', 'days_pending',
        'urgent_indicator', 'next_approver'
    ]
    
    list_filter = [
        'status', 'approval_status', 'urgent',
        ('created_at', admin.DateFieldListFilter),
        ('approval_submitted_at', admin.DateFieldListFilter)
    ]
    
    search_fields = [
        'po_number', 'supplier__name', 'created_by__username',
        'approvals__approver__username'
    ]
    
    inlines = [PurchaseOrderApprovalInline]
    
    fieldsets = (
        ('Purchase Order Details', {
            'fields': (
                'po_number', 'supplier', 'total_amount', 'currency',
                'expected_delivery_date'
            )
        }),
        ('Approval Workflow', {
            'fields': (
                'approval_status', 'approval_submitted_at', 'approval_completed_at',
                'approval_notes', 'urgent', 'escalation_reason'
            )
        }),
        ('Risk Assessment', {
            'fields': (
                'risk_score', 'compliance_checked', 'budget_approved',
                'supplier_verified'
            ),
            'classes': ('collapse',)
        })
    )
    
    actions = [
        'submit_for_approval', 'escalate_urgent', 'bulk_approve',
        'request_budget_check', 'notify_approvers', 'generate_approval_report'
    ]
    
    def get_urls(self):
        """Add workflow-specific URLs."""
        urls = super().get_urls()
        custom_urls = [
            path(
                'approval-queue/',
                self.admin_site.admin_view(self.approval_queue_view),
                name='po-approval-queue'
            ),
            path(
                '<int:po_id>/approve-level/',
                self.admin_site.admin_view(self.approve_level),
                name='po-approve-level'
            ),
            path(
                '<int:po_id>/reject/',
                self.admin_site.admin_view(self.reject_po),
                name='po-reject'
            ),
            path(
                '<int:po_id>/escalate/',
                self.admin_site.admin_view(self.escalate_po),
                name='po-escalate'
            ),
            path(
                'approval-analytics/',
                self.admin_site.admin_view(self.approval_analytics),
                name='po-approval-analytics'
            ),
        ]
        return custom_urls + urls
    
    def approval_status_display(self, obj):
        """Show approval status with workflow progress."""
        status_colors = {
            'NOT_SUBMITTED': 'gray',
            'PENDING_LEVEL_1': 'orange',
            'PENDING_LEVEL_2': 'blue',
            'PENDING_LEVEL_3': 'purple',
            'APPROVED': 'green',
            'REJECTED': 'red',
            'CANCELLED': 'gray'
        }
        
        color = status_colors.get(obj.approval_status, 'black')
        
        # Add urgency indicator
        urgency = "🚨 " if obj.urgent else ""
        
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}● {}</span>',
            color, urgency, obj.get_approval_status_display()
        )
    approval_status_display.short_description = 'Approval Status'
    
    def current_approval_level(self, obj):
        """Show current approval level with approver."""
        if obj.approval_status == 'APPROVED':
            return format_html('<span style="color: green;">✅ Completed</span>')
        elif obj.approval_status == 'REJECTED':
            return format_html('<span style="color: red;">❌ Rejected</span>')
        elif obj.approval_status == 'NOT_SUBMITTED':
            return format_html('<span style="color: gray;">Not Submitted</span>')
        
        # Extract level from status
        level_mapping = {
            'PENDING_LEVEL_1': 1,
            'PENDING_LEVEL_2': 2,
            'PENDING_LEVEL_3': 3
        }
        
        current_level = level_mapping.get(obj.approval_status, 0)
        if current_level > 0:
            next_approval = obj.approvals.filter(
                approval_level=current_level,
                status='PENDING'
            ).first()
            
            if next_approval:
                return format_html(
                    '<strong>Level {}</strong><br/><small>{}</small>',
                    current_level,
                    next_approval.approver.get_full_name()
                )
        
        return f'Level {current_level}'
    current_approval_level.short_description = 'Current Level'
    
    def approval_progress(self, obj):
        """Show approval progress bar."""
        total_levels = obj.approvals.count()
        approved_levels = obj.approvals.filter(status='APPROVED').count()
        
        if total_levels == 0:
            return 'No workflow'
        
        progress_percentage = (approved_levels / total_levels) * 100
        
        # Create visual progress bar
        filled_bars = int(progress_percentage / 20)  # 5 bars total
        empty_bars = 5 - filled_bars
        
        progress_bar = '█' * filled_bars + '░' * empty_bars
        
        color = 'green' if progress_percentage == 100 else 'blue'
        
        return format_html(
            '<span style="color: {}; font-family: monospace;">{}</span><br/>'
            '<small>{}/{} levels</small>',
            color, progress_bar, approved_levels, total_levels
        )
    approval_progress.short_description = 'Progress'
    
    def days_pending(self, obj):
        """Calculate days pending approval."""
        if obj.approval_submitted_at:
            if obj.approval_status == 'APPROVED':
                if obj.approval_completed_at:
                    days = (obj.approval_completed_at - obj.approval_submitted_at).days
                    return format_html(
                        '<span style="color: green;">{} days (completed)</span>',
                        days
                    )
            else:
                days = (timezone.now() - obj.approval_submitted_at).days
                
                # Color code based on urgency
                if days > 7:
                    color = 'red'
                elif days > 3:
                    color = 'orange'
                else:
                    color = 'blue'
                
                return format_html(
                    '<span style="color: {}; font-weight: bold;">{} days</span>',
                    color, days
                )
        
        return 'Not submitted'
    days_pending.short_description = 'Pending Days'
    
    def urgent_indicator(self, obj):
        """Show urgency indicator."""
        if obj.urgent:
            return format_html(
                '<span style="color: red; font-size: 1.2em;" title="Urgent">🚨</span>'
            )
        
        # Check if overdue
        if obj.expected_delivery_date and obj.expected_delivery_date < timezone.now().date():
            return format_html(
                '<span style="color: orange; font-size: 1.2em;" title="Overdue">⏰</span>'
            )
        
        return ''
    urgent_indicator.short_description = 'Urgent'
    
    def next_approver(self, obj):
        """Show next approver in workflow."""
        if obj.approval_status in ['APPROVED', 'REJECTED', 'NOT_SUBMITTED']:
            return 'N/A'
        
        # Get current pending approval
        level_mapping = {
            'PENDING_LEVEL_1': 1,
            'PENDING_LEVEL_2': 2,
            'PENDING_LEVEL_3': 3
        }
        
        current_level = level_mapping.get(obj.approval_status, 0)
        if current_level > 0:
            next_approval = obj.approvals.filter(
                approval_level=current_level,
                status='PENDING'
            ).first()
            
            if next_approval:
                return format_html(
                    '<a href="mailto:{}" title="Send email">{}</a><br/>'
                    '<small>{}</small>',
                    next_approval.approver.email,
                    next_approval.approver.get_full_name(),
                    next_approval.approver.get_role_display() if hasattr(next_approval.approver, 'get_role_display') else ''
                )
        
        return 'Not assigned'
    next_approver.short_description = 'Next Approver'
    
    def submit_for_approval(self, request, queryset):
        """Submit POs for approval."""
        submitted = 0
        for po in queryset.filter(approval_status='NOT_SUBMITTED'):
            po.approval_status = 'PENDING_LEVEL_1'
            po.approval_submitted_at = timezone.now()
            po.save()
            
            # Send notification to first level approvers
            self._notify_approvers(po, 1)
            submitted += 1
        
        self.message_user(
            request,
            f'{submitted} purchase orders submitted for approval.',
            messages.SUCCESS
        )
    submit_for_approval.short_description = "Submit for approval"
    
    def escalate_urgent(self, request, queryset):
        """Mark POs as urgent and escalate."""
        escalated = 0
        for po in queryset:
            po.urgent = True
            po.escalation_reason = "Manually escalated by admin"
            po.save()
            
            # Notify all approvers
            self._notify_urgent_escalation(po)
            escalated += 1
        
        self.message_user(
            request,
            f'{escalated} purchase orders marked as urgent.',
            messages.WARNING
        )
    escalate_urgent.short_description = "Mark as urgent"
    
    def bulk_approve(self, request, queryset):
        """Bulk approve POs (admin override)."""
        if not request.user.has_perm('inventory.can_bulk_approve_pos'):
            self.message_user(
                request,
                'You do not have permission to bulk approve purchase orders.',
                messages.ERROR
            )
            return
        
        approved = 0
        for po in queryset.filter(
            approval_status__in=['PENDING_LEVEL_1', 'PENDING_LEVEL_2', 'PENDING_LEVEL_3']
        ):
            po.approval_status = 'APPROVED'
            po.approval_completed_at = timezone.now()
            po.status = 'APPROVED'
            po.save()
            
            # Create approval record
            po.approvals.create(
                approver=request.user,
                approval_level=999,  # Admin override level
                status='APPROVED',
                comments='Bulk approved by admin',
                approved_amount=po.total_amount,
                approved_at=timezone.now()
            )
            
            approved += 1
        
        self.message_user(
            request,
            f'{approved} purchase orders bulk approved.',
            messages.SUCCESS
        )
    bulk_approve.short_description = "Bulk approve (Admin override)"
    
    def _notify_approvers(self, po, level):
        """Send notification to approvers at specific level."""
        approvals = po.approvals.filter(
            approval_level=level,
            status='PENDING'
        )
        
        for approval in approvals:
            # Send email notification
            subject = f'Purchase Order Approval Required: {po.po_number}'
            
            html_message = render_to_string('inventory/emails/po_approval_required.html', {
                'po': po,
                'approver': approval.approver,
                'approval_url': f'/admin/inventory/purchaseorder/{po.id}/change/',
                'urgent': po.urgent
            })
            
            send_mail(
                subject=subject,
                message='',
                html_message=html_message,
                from_email='noreply@company.com',
                recipient_list=[approval.approver.email],
                fail_silently=True
            )
    
    def _notify_urgent_escalation(self, po):
        """Send urgent escalation notifications."""
        # Notify all pending approvers
        pending_approvals = po.approvals.filter(status='PENDING')
        
        for approval in pending_approvals:
            subject = f'URGENT: Purchase Order Approval Required: {po.po_number}'
            
            html_message = render_to_string('inventory/emails/po_urgent_escalation.html', {
                'po': po,
                'approver': approval.approver,
                'escalation_reason': po.escalation_reason
            })
            
            send_mail(
                subject=subject,
                message='',
                html_message=html_message,
                from_email='noreply@company.com',
                recipient_list=[approval.approver.email],
                fail_silently=True
            )
    
    def approval_queue_view(self, request):
        """Show approval queue dashboard."""
        # Get user's pending approvals
        user_approvals = PurchaseOrderApproval.objects.filter(
            approver=request.user,
            status='PENDING'
        ).select_related('purchase_order', 'purchase_order__supplier')
        
        # Get queue statistics
        queue_stats = {
            'total_pending': user_approvals.count(),
            'urgent_count': user_approvals.filter(purchase_order__urgent=True).count(),
            'overdue_count': user_approvals.filter(
                purchase_order__approval_submitted_at__lt=timezone.now() - timezone.timedelta(days=7)
            ).count()
        }
        
        return JsonResponse({
            'approvals': [
                {
                    'po_number': approval.purchase_order.po_number,
                    'supplier': approval.purchase_order.supplier.name,
                    'amount': float(approval.purchase_order.total_amount),
                    'days_pending': (timezone.now() - approval.purchase_order.approval_submitted_at).days,
                    'urgent': approval.purchase_order.urgent
                }
                for approval in user_approvals
            ],
            'stats': queue_stats
        })