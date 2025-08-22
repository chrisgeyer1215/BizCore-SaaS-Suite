# ============================================================================
# backend/apps/crm/admin/lead.py - Enhanced Lead Management Admin
# ============================================================================

from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.db.models import Count, Avg
from django.utils import timezone
from datetime import timedelta

from .base import TenantAwareAdmin, EnhancedTabularInline, AdvancedDateRangeFilter
from ..models import Lead, LeadSource, LeadScoringRule, Activity


class ActivityInline(EnhancedTabularInline):
    """Inline admin for lead activities"""
    model = Activity
    fields = ['activity_type', 'subject', 'status', 'start_datetime', 'assigned_to']
    readonly_fields = ['created_at']
    ordering = ['-created_at']
    extra = 0


class LeadAdmin(TenantAwareAdmin):
    """Comprehensive lead management admin with advanced features"""
    
    list_display = [
        'full_name', 'company', 'email', 'phone', 'source', 'status',
        'score_display', 'assigned_to', 'created_at', 'last_activity',
        'conversion_status', 'status_indicator'
    ]
    
    list_filter = [
        'status', 'source', 'assigned_to', 'is_active',
        AdvancedDateRangeFilter, 'lead_scoring_rules'
    ]
    
    search_fields = [
        'first_name', 'last_name', 'email', 'phone', 'company',
        'job_title', 'industry', 'notes'
    ]
    
    list_editable = ['status', 'assigned_to']
    list_select_related = ['source', 'assigned_to', 'territory']
    list_prefetch_related = ['activities', 'lead_scoring_rules']
    
    fieldsets = (
        ('Personal Information', {
            'fields': (
                ('first_name', 'last_name'),
                ('email', 'phone', 'mobile_phone'),
                ('job_title', 'company'),
                'website'
            )
        }),
        ('Address Information', {
            'fields': (
                'address_line_1', 'address_line_2',
                ('city', 'state', 'postal_code'),
                'country'
            ),
            'classes': ('collapse',)
        }),
        ('Lead Details', {
            'fields': (
                ('status', 'source'),
                ('assigned_to', 'territory'),
                ('score', 'grade'),
                'industry'
            )
        }),
        ('Conversion Information', {
            'fields': (
                ('converted_account', 'converted_contact', 'converted_opportunity'),
                ('converted_at', 'converted_by')
            ),
            'classes': ('collapse',)
        }),
        ('Additional Information', {
            'fields': ('notes', 'tags'),
            'classes': ('collapse',)
        }),
        ('System Information', {
            'fields': (
                ('created_at', 'updated_at'),
                ('created_by', 'updated_by'),
                'last_scored_at'
            ),
            'classes': ('collapse',)
        })
    )
    
    readonly_fields = [
        'created_at', 'updated_at', 'created_by', 'updated_by',
        'converted_at', 'converted_by', 'last_scored_at', 'last_activity'
    ]
    
    inlines = [ActivityInline]
    
    actions = [
        'assign_to_me', 'bulk_score_calculation', 'mark_as_qualified',
        'mark_as_unqualified', 'bulk_nurturing_sequence', 'export_leads'
    ]
    
    def get_queryset(self, request):
        """Optimized queryset with annotations"""
        return super().get_queryset(request).select_related(
            'source', 'assigned_to', 'territory', 'converted_account'
        ).prefetch_related(
            'activities'
        ).annotate(
            activity_count=Count('activities'),
            avg_score=Avg('score')
        )
    
    def score_display(self, obj):
        """Enhanced score display with visual indicators"""
        if obj.score is None:
            return format_html('<span style="color: gray;">Not Scored</span>')
        
        if obj.score >= 80:
            color = 'red'
            icon = '🔥'  # Hot lead
        elif obj.score >= 60:
            color = 'orange'
            icon = '⚡'  # Warm lead
        elif obj.score >= 40:
            color = 'blue'
            icon = '💧'  # Cool lead
        else:
            color = 'gray'
            icon = '❄️'  # Cold lead
        
        return format_html(
            '<span style="color: {}; font-weight: bold;">{} {}</span>',
            color, icon, obj.score
        )
    
    score_display.short_description = 'Score'
    score_display.admin_order_field = 'score'
    
    def last_activity(self, obj):
        """Display last activity information"""
        last_activity = obj.activities.order_by('-created_at').first()
        if last_activity:
            return format_html(
                '<span title="{}">{}</span>',
                last_activity.subject,
                last_activity.created_at.strftime('%m/%d/%Y')
            )
        return 'No activities'
    
    last_activity.short_description = 'Last Activity'
    
    def conversion_status(self, obj):
        """Display conversion status with links"""
        if obj.converted_account:
            account_url = reverse('admin:crm_account_change', args=[obj.converted_account.id])
            return format_html(
                '<a href="{}">✅ Converted</a>',
                account_url
            )
        return '⏳ Not Converted'
    
    conversion_status.short_description = 'Conversion'
    
    # Admin actions
    def assign_to_me(self, request, queryset):
        """Assign selected leads to current user"""
        updated = queryset.update(
            assigned_to=request.user,
            assigned_at=timezone.now()
        )
        self.message_user(request, f'{updated} leads assigned to you.')
    
    assign_to_me.short_description = "Assign selected leads to me"
    
    def bulk_score_calculation(self, request, queryset):
        """Trigger bulk lead scoring"""
        from ..tasks.lead_tasks import calculate_lead_scores
        
        lead_ids = list(queryset.values_list('id', flat=True))
        
        # Queue scoring task
        calculate_lead_scores.delay(
            lead_ids=lead_ids,
            security_context={
                'tenant_id': request.tenant.id,
                'user_id': request.user.id,
                'permissions': [],
                'timestamp': timezone.now().isoformat()
            }
        )
        
        self.message_user(request, f'Scoring queued for {len(lead_ids)} leads.')
    
    bulk_score_calculation.short_description = "Calculate scores for selected leads"
    
    def mark_as_qualified(self, request, queryset):
        """Mark leads as qualified"""
        updated = queryset.update(
            status='QUALIFIED',
            qualified_at=timezone.now(),
            qualified_by=request.user
        )
        self.message_user(request, f'{updated} leads marked as qualified.')
    
    mark_as_qualified.short_description = "Mark as qualified"
    
    def bulk_nurturing_sequence(self, request, queryset):
        """Start nurturing sequence for selected leads"""
        from ..tasks.lead_tasks import lead_nurturing_sequence
        
        security_context = {
            'tenant_id': request.tenant.id,
            'user_id': request.user.id,
            'permissions': [],
            'timestamp': timezone.now().isoformat()
        }
        
        for lead in queryset:
            # Determine sequence type based on lead score
            if lead.score and lead.score < 40:
                sequence_type = 'cold_lead'
            else:
                sequence_type = 'new_lead'
            
            lead_nurturing_sequence.delay(
                lead_id=lead.id,
                sequence_type=sequence_type,
                security_context=security_context
            )
        
        self.message_user(request, f'Nurturing sequences started for {queryset.count()} leads.')
    
    bulk_nurturing_sequence.short_description = "Start nurturing sequence"


class LeadSourceAdmin(TenantAwareAdmin):
    """Enhanced lead source management"""
    
    list_display = [
        'name', 'source_type', 'is_active', 'cost_per_lead',
        'total_leads', 'conversion_rate', 'roi_display', 'status_indicator'
    ]
    
    list_filter = ['source_type', 'is_active', 'created_at']
    search_fields = ['name', 'description']
    list_editable = ['is_active', 'cost_per_lead']
    
    fieldsets = (
        ('Source Information', {
            'fields': ('name', 'source_type', 'description', 'is_active')
        }),
        ('Performance Tracking', {
            'fields': ('cost_per_lead', 'expected_conversion_rate', 'tracking_code')
        }),
        ('Configuration', {
            'fields': ('auto_assignment_enabled', 'default_assigned_user', 'lead_scoring_boost'),
            'classes': ('collapse',)
        })
    )
    
    def get_queryset(self, request):
        """Add performance annotations"""
        return super().get_queryset(request).annotate(
            lead_count=Count('leads'),
            converted_count=Count('leads', filter=models.Q(leads__converted_account__isnull=False))
        )
    
    def total_leads(self, obj):
        """Display total leads from this source"""
        return obj.lead_count
    
    total_leads.short_description = 'Total Leads'
    total_leads.admin_order_field = 'lead_count'
    
    def conversion_rate(self, obj):
        """Calculate and display conversion rate"""
        if obj.lead_count > 0:
            rate = (obj.converted_count / obj.lead_count) * 100
            return f'{rate:.1f}%'
        return '0%'
    
    conversion_rate.short_description = 'Conversion Rate'
    
    def roi_display(self, obj):
        """Calculate and display ROI"""
        if obj.cost_per_lead and obj.converted_count > 0:
            # Simplified ROI calculation (would be more complex in reality)
            total_cost = obj.cost_per_lead * obj.lead_count
            # Assume average deal value (would come from actual data)
            avg_deal_value = 5000
            total_revenue = avg_deal_value * obj.converted_count
            
            if total_cost > 0:
                roi = ((total_revenue - total_cost) / total_cost) * 100
                return f'{roi:.1f}%'
        
        return 'N/A'
    
    roi_display.short_description = 'ROI'


class LeadScoringRuleAdmin(TenantAwareAdmin):
    """Enhanced lead scoring rule management"""
    
    list_display = [
        'name', 'rule_type', 'weight', 'is_active', 'priority',
        'created_at', 'status_indicator'
    ]
    
    list_filter = ['rule_type', 'is_active', 'priority']
    search_fields = ['name', 'description']
    list_editable = ['weight', 'is_active', 'priority']
    
    fieldsets = (
        ('Rule Information', {
            'fields': ('name', 'description', 'rule_type', 'is_active')
        }),
        ('Scoring Configuration', {
            'fields': ('weight', 'priority', 'criteria')
        }),
        ('Advanced Settings', {
            'fields': ('conditions', 'effective_date', 'expiry_date'),
            'classes': ('collapse',)
        })
    )
    
    def get_form(self, request, obj=None, **kwargs):
        """Customize form with JSON field editor"""
        form = super().get_form(request, obj, **kwargs)
        
        # Add help text for JSON fields
        if 'criteria' in form.base_fields:
            form.base_fields['criteria'].help_text = """
            JSON configuration for scoring criteria. Example:
            {
                "job_titles": {
                    "high_value": ["CEO", "CTO", "VP"],
                    "medium_value": ["Director", "Manager"]
                },
                "company_size": {
                    "Enterprise": 30,
                    "Mid-Market": 20,
                    "SMB": 10
                }
            }
            """
        
        return form