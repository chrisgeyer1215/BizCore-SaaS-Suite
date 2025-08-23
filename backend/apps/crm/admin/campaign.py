# ============================================================================
# backend/apps/crm/admin/campaign.py - Advanced Campaign Management Admin
# ============================================================================

from django.contrib import admin
from django.utils.html import format_html
from django.db.models import Count, Sum, Avg, Q
from django.utils import timezone
from django.contrib import messages
from datetime import timedelta

from .base import TenantAwareAdmin, EnhancedTabularInline, AdvancedDateRangeFilter
from ..models import (
    Campaign, CampaignMember, EmailTemplate, CampaignEmail,
    Lead, Contact, Account
)


class CampaignMemberInline(EnhancedTabularInline):
    """Inline admin for campaign members"""
    model = CampaignMember
    fields = ['contact', 'email', 'status', 'joined_at', 'responded_at']
    readonly_fields = ['joined_at', 'responded_at']
    extra = 0


class CampaignEmailInline(EnhancedTabularInline):
    """Inline admin for campaign emails"""
    model = CampaignEmail
    fields = ['email_template', 'scheduled_at', 'status', 'sent_count']
    readonly_fields = ['sent_count']
    extra = 0


class CampaignAdmin(TenantAwareAdmin):
    """Comprehensive campaign management admin"""
    
    list_display = [
        'name', 'campaign_type', 'status', 'start_date', 'end_date',
        'member_count', 'response_rate', 'budget_spent', 'roi_display', 
        'status_indicator'
    ]
    
    list_filter = [
        'campaign_type', 'status', 'start_date', 'end_date',
        AdvancedDateRangeFilter, 'is_active'
    ]
    
    search_fields = ['name', 'description', 'campaign_code']
    
    list_editable = ['status', 'start_date', 'end_date']
    list_select_related = ['created_by', 'assigned_to']
    
    fieldsets = (
        ('Campaign Information', {
            'fields': (
                ('name', 'campaign_code'),
                ('campaign_type', 'status'),
                ('start_date', 'end_date'),
                ('assigned_to', 'owner')
            )
        }),
        ('Target & Goals', {
            'fields': (
                ('target_audience', 'expected_members'),
                ('expected_response_rate', 'expected_revenue'),
                'success_metrics'
            )
        }),
        ('Budget & Costs', {
            'fields': (
                ('budgeted_cost', 'actual_cost'),
                ('cost_per_lead', 'cost_per_acquisition'),
                'budget_approval_status'
            )
        }),
        ('Content & Messaging', {
            'fields': (
                'description', 'marketing_message',
                'call_to_action', 'landing_page_url'
            ),
            'classes': ('collapse',)
        }),
        ('Automation Settings', {
            'fields': (
                ('auto_add_leads', 'auto_nurture_enabled'),
                ('follow_up_sequence', 'drip_campaign_enabled'),
                'automation_rules'
            ),
            'classes': ('collapse',)
        }),
        ('System Information', {
            'fields': (
                ('created_at', 'updated_at'),
                ('created_by', 'updated_by'),
                ('last_activity_date', 'completion_percentage')
            ),
            'classes': ('collapse',)
        })
    )
    
    readonly_fields = [
        'created_at', 'updated_at', 'created_by', 'updated_by',
        'last_activity_date', 'completion_percentage'
    ]
    
    inlines = [CampaignMemberInline, CampaignEmailInline]
    
    actions = [
        'activate_campaigns', 'pause_campaigns', 'clone_campaign',
        'add_leads_to_campaign', 'send_campaign_emails', 'calculate_roi'
    ]
    
    def get_queryset(self, request):
        """Optimized queryset with annotations"""
        return super().get_queryset(request).select_related(
            'assigned_to', 'created_by'
        ).prefetch_related(
            'members', 'emails'
        ).annotate(
            total_members=Count('members'),
            responded_members=Count('members', filter=Q(members__status='responded')),
            total_leads=Count('members', filter=Q(members__lead__isnull=False))
        )
    
    def member_count(self, obj):
        """Display member count with breakdown"""
        total = obj.total_members
        responded = obj.responded_members
        leads = obj.total_leads
        
        return format_html(
            '<strong>{}</strong> total<br/>'
            '<span style="color: green;">{}</span> responded<br/>'
            '<span style="color: blue;">{}</span> leads',
            total, responded, leads
        )
    
    member_count.short_description = 'Members'
    member_count.admin_order_field = 'total_members'
    
    def response_rate(self, obj):
        """Calculate and display response rate"""
        if obj.total_members > 0:
            rate = (obj.responded_members / obj.total_members) * 100
            
            if rate >= 10:  # Excellent response rate
                color = 'green'
                icon = '🔥'
            elif rate >= 5:  # Good response rate
                color = 'blue'
                icon = '👍'
            elif rate >= 2:  # Average response rate
                color = 'orange'
                icon = '⚡'
            else:  # Poor response rate
                color = 'red'
                icon = '📉'
            
            return format_html(
                '<span style="color: {}; font-weight: bold;">{} {:.1f}%</span>',
                color, icon, rate
            )
        return '0%'
    
    response_rate.short_description = 'Response Rate'
    
    def budget_spent(self, obj):
        """Display budget information"""
        if obj.actual_cost and obj.budgeted_cost:
            percentage = (obj.actual_cost / obj.budgeted_cost) * 100
            
            if percentage > 100:
                color = 'red'
                status = 'Over budget'
            elif percentage > 80:
                color = 'orange'
                status = 'Near budget'
            else:
                color = 'green'
                status = 'Under budget'
            
            return format_html(
                '${:,.2f} / ${:,.2f}<br/>'
                '<small style="color: {};">{}</small>',
                obj.actual_cost, obj.budgeted_cost, color, status
            )
        elif obj.actual_cost:
            return format_html('${:,.2f}', obj.actual_cost)
        return 'Not set'
    
    budget_spent.short_description = 'Budget'
    
    def roi_display(self, obj):
        """Calculate and display ROI"""
        if obj.actual_cost and hasattr(obj, 'generated_revenue'):
            if obj.actual_cost > 0:
                roi = ((obj.generated_revenue - obj.actual_cost) / obj.actual_cost) * 100
                
                if roi > 300:  # Excellent ROI
                    color = 'green'
                    icon = '🚀'
                elif roi > 100:  # Good ROI
                    color = 'blue'
                    icon = '📈'
                elif roi > 0:  # Positive ROI
                    color = 'orange'
                    icon = '➕'
                else:  # Negative ROI
                    color = 'red'
                    icon = '📉'
                
                return format_html(
                    '<span style="color: {}; font-weight: bold;">{} {:.1f}%</span>',
                    color, icon, roi
                )
        return 'TBD'
    
    roi_display.short_description = 'ROI'
    
    # Admin Actions
    def activate_campaigns(self, request, queryset):
        """Activate selected campaigns"""
        updated = queryset.update(
            status='active',
            start_date=timezone.now().date()
        )
        self.message_user(request, f'{updated} campaigns activated.')
    
    activate_campaigns.short_description = "Activate campaigns"
    
    def pause_campaigns(self, request, queryset):
        """Pause selected campaigns"""
        updated = queryset.update(status='paused')
        self.message_user(request, f'{updated} campaigns paused.')
    
    pause_campaigns.short_description = "Pause campaigns"
    
    def clone_campaign(self, request, queryset):
        """Clone selected campaigns"""
        from ..tasks.campaign_tasks import clone_campaign_task
        
        security_context = {
            'tenant_id': request.tenant.id,
            'user_id': request.user.id,
            'permissions': [],
            'timestamp': timezone.now().isoformat()
        }
        
        for campaign in queryset:
            clone_campaign_task.delay(
                campaign_id=campaign.id,
                new_name=f"{campaign.name} (Clone)",
                security_context=security_context
            )
        
        self.message_user(request, f'Cloning queued for {queryset.count()} campaigns.')
    
    clone_campaign.short_description = "Clone campaigns"
    
    def add_leads_to_campaign(self, request, queryset):
        """Add qualified leads to selected campaigns"""
        from ..tasks.campaign_tasks import add_leads_to_campaigns
        
        security_context = {
            'tenant_id': request.tenant.id,
            'user_id': request.user.id,
            'permissions': [],
            'timestamp': timezone.now().isoformat()
        }
        
        campaign_ids = list(queryset.values_list('id', flat=True))
        add_leads_to_campaigns.delay(
            campaign_ids=campaign_ids,
            lead_criteria={'status': 'qualified'},
            security_context=security_context
        )
        
        self.message_user(request, f'Lead addition queued for {len(campaign_ids)} campaigns.')
    
    add_leads_to_campaign.short_description = "Add qualified leads"
    
    def send_campaign_emails(self, request, queryset):
        """Send campaign emails"""
        from ..tasks.campaign_tasks import send_campaign_emails_task
        
        security_context = {
            'tenant_id': request.tenant.id,
            'user_id': request.user.id,
            'permissions': [],
            'timestamp': timezone.now().isoformat()
        }
        
        for campaign in queryset.filter(status='active'):
            send_campaign_emails_task.delay(
                campaign_id=campaign.id,
                security_context=security_context
            )
        
        self.message_user(request, f'Email sending queued for {queryset.count()} campaigns.')
    
    send_campaign_emails.short_description = "Send campaign emails"


class CampaignMemberAdmin(TenantAwareAdmin):
    """Campaign member management admin"""
    
    list_display = [
        'campaign', 'contact_name', 'email', 'status', 'joined_at',
        'responded_at', 'lead_generated', 'revenue_attributed', 'status_indicator'
    ]
    
    list_filter = [
        'status', 'campaign', 'joined_at',
        AdvancedDateRangeFilter, 'lead_generated'
    ]
    
    search_fields = [
        'email', 'contact__first_name', 'contact__last_name',
        'campaign__name'
    ]
    
    readonly_fields = ['joined_at', 'responded_at', 'last_email_sent']
    
    def contact_name(self, obj):
        """Display contact name with link"""
        if obj.contact:
            url = reverse('admin:crm_contact_change', args=[obj.contact.id])
            return format_html(
                '<a href="{}">{} {}</a>',
                url, obj.contact.first_name, obj.contact.last_name
            )
        return obj.email
    
    contact_name.short_description = 'Contact'
    
    def lead_generated(self, obj):
        """Show if lead was generated"""
        if obj.lead:
            return format_html(
                '<span style="color: green;">✓ Generated</span>'
            )
        return format_html(
            '<span style="color: gray;">No lead</span>'
        )
    
    lead_generated.short_description = 'Lead Status'
    
    def revenue_attributed(self, obj):
        """Display attributed revenue"""
        if hasattr(obj, 'attributed_revenue') and obj.attributed_revenue:
            return format_html('${:,.2f}', obj.attributed_revenue)
        return '$0.00'
    
    revenue_attributed.short_description = 'Revenue'


class EmailTemplateAdmin(TenantAwareAdmin):
    """Email template management admin"""
    
    list_display = [
        'name', 'template_type', 'is_active', 'usage_count',
        'open_rate', 'click_rate', 'created_at', 'status_indicator'
    ]
    
    list_filter = ['template_type', 'is_active', 'created_at']
    search_fields = ['name', 'subject', 'description']
    
    fieldsets = (
        ('Template Information', {
            'fields': (
                ('name', 'template_type'),
                ('subject', 'is_active'),
                'description'
            )
        }),
        ('Content', {
            'fields': (
                'html_content', 'text_content',
                'preheader_text'
            )
        }),
        ('Design Settings', {
            'fields': (
                ('header_image_url', 'footer_text'),
                ('primary_color', 'secondary_color'),
                'custom_css'
            ),
            'classes': ('collapse',)
        }),
        ('Personalization', {
            'fields': (
                'merge_fields', 'dynamic_content_rules',
                'personalization_settings'
            ),
            'classes': ('collapse',)
        })
    )
    
    def get_queryset(self, request):
        """Add usage statistics"""
        return super().get_queryset(request).annotate(
            email_count=Count('campaign_emails'),
            total_opens=Sum('campaign_emails__open_count'),
            total_clicks=Sum('campaign_emails__click_count'),
            total_sent=Sum('campaign_emails__sent_count')
        )
    
    def usage_count(self, obj):
        """Display usage count"""
        return obj.email_count
    
    usage_count.short_description = 'Used'
    usage_count.admin_order_field = 'email_count'
    
    def open_rate(self, obj):
        """Calculate open rate"""
        if obj.total_sent and obj.total_opens:
            rate = (obj.total_opens / obj.total_sent) * 100
            
            if rate >= 25:  # Excellent open rate
                color = 'green'
            elif rate >= 20:  # Good open rate
                color = 'blue'
            elif rate >= 15:  # Average open rate
                color = 'orange'
            else:  # Poor open rate
                color = 'red'
            
            return format_html(
                '<span style="color: {};">{:.1f}%</span>',
                color, rate
            )
        return 'No data'
    
    open_rate.short_description = 'Open Rate'
    
    def click_rate(self, obj):
        """Calculate click rate"""
        if obj.total_sent and obj.total_clicks:
            rate = (obj.total_clicks / obj.total_sent) * 100
            
            if rate >= 5:  # Excellent click rate
                color = 'green'
            elif rate >= 3:  # Good click rate
                color = 'blue'
            elif rate >= 1:  # Average click rate
                color = 'orange'
            else:  # Poor click rate
                color = 'red'
            
            return format_html(
                '<span style="color: {};">{:.1f}%</span>',
                color, rate
            )
        return 'No data'
    
    click_rate.short_description = 'Click Rate'