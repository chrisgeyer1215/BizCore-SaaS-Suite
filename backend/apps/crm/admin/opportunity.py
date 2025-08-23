# ============================================================================
# backend/apps/crm/admin/opportunity.py - Advanced Opportunity Management Admin
# ============================================================================

from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.db.models import Count, Sum, Avg, Q
from django.utils import timezone
from django.contrib import messages
from datetime import timedelta
import json

from .base import TenantAwareAdmin, EnhancedTabularInline, AdvancedDateRangeFilter
from ..models import (
    Opportunity, Pipeline, PipelineStage, OpportunityProduct, 
    Activity, Contact, Account
)


class OpportunityProductInline(EnhancedTabularInline):
    """Inline admin for opportunity products"""
    model = OpportunityProduct
    fields = ['product', 'quantity', 'unit_price', 'discount_percent', 'total_price']
    readonly_fields = ['total_price']
    extra = 0

    def total_price(self, obj):
        """Calculate total price with discount"""
        if obj.quantity and obj.unit_price:
            subtotal = obj.quantity * obj.unit_price
            if obj.discount_percent:
                discount = subtotal * (obj.discount_percent / 100)
                return subtotal - discount
            return subtotal
        return 0
    
    total_price.short_description = 'Total'


class ActivityInline(EnhancedTabularInline):
    """Inline admin for opportunity activities"""
    model = Activity
    fields = ['activity_type', 'subject', 'status', 'start_datetime', 'assigned_to']
    readonly_fields = ['created_at']
    ordering = ['-created_at']
    extra = 0


class OpportunityAdmin(TenantAwareAdmin):
    """Comprehensive opportunity management admin"""
    
    list_display = [
        'name', 'account', 'stage', 'amount_display', 'probability',
        'expected_close_date', 'assigned_to', 'age_display', 'last_activity_date',
        'status_indicator'
    ]
    
    list_filter = [
        'stage', 'probability', 'lead_source', 'assigned_to',
        AdvancedDateRangeFilter, 'pipeline', 'is_active'
    ]
    
    search_fields = [
        'name', 'account__name', 'description', 'assigned_to__username',
        'contact__first_name', 'contact__last_name'
    ]
    
    list_editable = ['stage', 'probability', 'expected_close_date']
    list_select_related = ['account', 'contact', 'assigned_to', 'pipeline', 'stage']
    list_prefetch_related = ['activities', 'products']
    
    fieldsets = (
        ('Opportunity Information', {
            'fields': (
                ('name', 'account'),
                ('contact', 'lead_source'),
                ('amount', 'currency'),
                ('expected_close_date', 'close_date')
            )
        }),
        ('Pipeline Management', {
            'fields': (
                ('pipeline', 'stage'),
                ('probability', 'forecast_category'),
                ('assigned_to', 'owner')
            )
        }),
        ('Sales Process', {
            'fields': (
                ('sales_process', 'current_step'),
                ('next_step', 'next_step_date'),
                'competitors'
            ),
            'classes': ('collapse',)
        }),
        ('Financial Details', {
            'fields': (
                ('budget_confirmed', 'authority_confirmed'),
                ('need_confirmed', 'timeline_confirmed'),
                'discount_amount'
            ),
            'classes': ('collapse',)
        }),
        ('Additional Information', {
            'fields': (
                'description', 'internal_notes', 'tags',
                'loss_reason', 'competitor_lost_to'
            ),
            'classes': ('collapse',)
        }),
        ('System Information', {
            'fields': (
                ('created_at', 'updated_at'),
                ('created_by', 'updated_by'),
                ('won_date', 'lost_date')
            ),
            'classes': ('collapse',)
        })
    )
    
    readonly_fields = [
        'created_at', 'updated_at', 'created_by', 'updated_by',
        'won_date', 'lost_date', 'age_display', 'last_activity_date'
    ]
    
    inlines = [OpportunityProductInline, ActivityInline]
    
    actions = [
        'assign_to_me', 'mark_as_won', 'mark_as_lost', 'advance_stage',
        'schedule_follow_up', 'bulk_forecast_update', 'generate_quotes'
    ]
    
    def get_queryset(self, request):
        """Optimized queryset with annotations"""
        return super().get_queryset(request).select_related(
            'account', 'contact', 'assigned_to', 'pipeline', 'stage', 'lead_source'
        ).prefetch_related(
            'activities', 'products'
        ).annotate(
            activity_count=Count('activities'),
            product_count=Count('products'),
            total_value=Sum('products__total_price')
        )
    
    def amount_display(self, obj):
        """Enhanced amount display with currency"""
        if obj.amount:
            currency = obj.currency or 'USD'
            
            # Color coding based on amount
            if obj.amount >= 100000:
                color = 'red'  # High value
                icon = '💎'
            elif obj.amount >= 50000:
                color = 'orange'  # Medium-high value
                icon = '🔥'
            elif obj.amount >= 10000:
                color = 'blue'  # Medium value
                icon = '💼'
            else:
                color = 'green'  # Lower value
                icon = '💰'
            
            return format_html(
                '<span style="color: {}; font-weight: bold;">{} {:,} {}</span>',
                color, icon, obj.amount, currency
            )
        return 'Not specified'
    
    amount_display.short_description = 'Amount'
    amount_display.admin_order_field = 'amount'
    
    def age_display(self, obj):
        """Display opportunity age"""
        if obj.created_at:
            age = timezone.now() - obj.created_at
            days = age.days
            
            if days < 30:
                color = 'green'
            elif days < 90:
                color = 'orange'
            else:
                color = 'red'
            
            return format_html(
                '<span style="color: {};">{} days</span>',
                color, days
            )
        return 'Unknown'
    
    age_display.short_description = 'Age'
    
    def last_activity_date(self, obj):
        """Display last activity date"""
        last_activity = obj.activities.order_by('-created_at').first()
        if last_activity:
            days_ago = (timezone.now().date() - last_activity.created_at.date()).days
            
            if days_ago == 0:
                return format_html('<span style="color: green;">Today</span>')
            elif days_ago <= 7:
                return format_html('<span style="color: blue;">{} days ago</span>', days_ago)
            elif days_ago <= 30:
                return format_html('<span style="color: orange;">{} days ago</span>', days_ago)
            else:
                return format_html('<span style="color: red;">{} days ago</span>', days_ago)
        
        return format_html('<span style="color: gray;">No activities</span>')
    
    last_activity_date.short_description = 'Last Activity'
    
    # Admin Actions
    def assign_to_me(self, request, queryset):
        """Assign selected opportunities to current user"""
        updated = queryset.update(
            assigned_to=request.user,
            updated_at=timezone.now()
        )
        self.message_user(request, f'{updated} opportunities assigned to you.')
    
    assign_to_me.short_description = "Assign selected opportunities to me"
    
    def mark_as_won(self, request, queryset):
        """Mark opportunities as won"""
        won_stage = PipelineStage.objects.filter(
            pipeline__is_default=True, 
            stage_type='won'
        ).first()
        
        if won_stage:
            updated = queryset.update(
                stage=won_stage,
                probability=100,
                won_date=timezone.now(),
                close_date=timezone.now().date()
            )
            self.message_user(request, f'{updated} opportunities marked as won.')
        else:
            self.message_user(request, 'No default won stage found.', level='ERROR')
    
    mark_as_won.short_description = "Mark as won"
    
    def mark_as_lost(self, request, queryset):
        """Mark opportunities as lost"""
        lost_stage = PipelineStage.objects.filter(
            pipeline__is_default=True,
            stage_type='lost'
        ).first()
        
        if lost_stage:
            updated = queryset.update(
                stage=lost_stage,
                probability=0,
                lost_date=timezone.now(),
                close_date=timezone.now().date()
            )
            self.message_user(request, f'{updated} opportunities marked as lost.')
        else:
            self.message_user(request, 'No default lost stage found.', level='ERROR')
    
    mark_as_lost.short_description = "Mark as lost"
    
    def advance_stage(self, request, queryset):
        """Advance opportunities to next stage"""
        for opportunity in queryset:
            current_stage = opportunity.stage
            if current_stage:
                next_stage = PipelineStage.objects.filter(
                    pipeline=current_stage.pipeline,
                    order__gt=current_stage.order
                ).order_by('order').first()
                
                if next_stage:
                    opportunity.stage = next_stage
                    opportunity.probability = next_stage.default_probability
                    opportunity.save()
        
        self.message_user(request, f'Advanced {queryset.count()} opportunities to next stage.')
    
    advance_stage.short_description = "Advance to next stage"
    
    def schedule_follow_up(self, request, queryset):
        """Schedule follow-up activities"""
        from ..tasks.activity_tasks import schedule_follow_up_activity
        
        security_context = {
            'tenant_id': request.tenant.id,
            'user_id': request.user.id,
            'permissions': [],
            'timestamp': timezone.now().isoformat()
        }
        
        for opportunity in queryset:
            schedule_follow_up_activity.delay(
                opportunity_id=opportunity.id,
                follow_up_days=7,
                activity_type='call',
                security_context=security_context
            )
        
        self.message_user(request, f'Follow-up activities scheduled for {queryset.count()} opportunities.')
    
    schedule_follow_up.short_description = "Schedule follow-up"
    
    def generate_quotes(self, request, queryset):
        """Generate quotes for selected opportunities"""
        from ..tasks.opportunity_tasks import generate_opportunity_quote
        
        security_context = {
            'tenant_id': request.tenant.id,
            'user_id': request.user.id,
            'permissions': [],
            'timestamp': timezone.now().isoformat()
        }
        
        for opportunity in queryset:
            if opportunity.products.exists():
                generate_opportunity_quote.delay(
                    opportunity_id=opportunity.id,
                    security_context=security_context
                )
        
        self.message_user(request, f'Quote generation queued for {queryset.count()} opportunities.')
    
    generate_quotes.short_description = "Generate quotes"


class PipelineAdmin(TenantAwareAdmin):
    """Pipeline management admin"""
    
    list_display = [
        'name', 'is_default', 'stage_count', 'opportunity_count',
        'total_value', 'avg_deal_size', 'status_indicator'
    ]
    
    list_filter = ['is_default', 'is_active', 'created_at']
    search_fields = ['name', 'description']
    
    fieldsets = (
        ('Pipeline Information', {
            'fields': ('name', 'description', 'is_default', 'is_active')
        }),
        ('Configuration', {
            'fields': ('sales_process_template', 'auto_advance_criteria')
        })
    )
    
    def get_queryset(self, request):
        """Add performance annotations"""
        return super().get_queryset(request).annotate(
            stage_count=Count('stages'),
            opportunity_count=Count('opportunities'),
            total_pipeline_value=Sum('opportunities__amount')
        )
    
    def stage_count(self, obj):
        """Display stage count"""
        return obj.stage_count
    
    stage_count.short_description = 'Stages'
    stage_count.admin_order_field = 'stage_count'
    
    def opportunity_count(self, obj):
        """Display opportunity count"""
        return obj.opportunity_count
    
    opportunity_count.short_description = 'Opportunities'
    opportunity_count.admin_order_field = 'opportunity_count'
    
    def total_value(self, obj):
        """Display total pipeline value"""
        if obj.total_pipeline_value:
            return format_html('${:,.2f}', obj.total_pipeline_value)
        return '$0.00'
    
    total_value.short_description = 'Total Value'
    total_value.admin_order_field = 'total_pipeline_value'
    
    def avg_deal_size(self, obj):
        """Calculate average deal size"""
        if obj.opportunity_count > 0 and obj.total_pipeline_value:
            avg = obj.total_pipeline_value / obj.opportunity_count
            return format_html('${:,.2f}', avg)
        return '$0.00'
    
    avg_deal_size.short_description = 'Avg Deal Size'


class PipelineStageAdmin(TenantAwareAdmin):
    """Pipeline stage management admin"""
    
    list_display = [
        'name', 'pipeline', 'order', 'stage_type', 'default_probability',
        'opportunity_count', 'total_value', 'avg_age', 'status_indicator'
    ]
    
    list_filter = ['stage_type', 'pipeline', 'is_active']
    search_fields = ['name', 'pipeline__name']
    list_editable = ['order', 'default_probability']
    ordering = ['pipeline', 'order']
    
    fieldsets = (
        ('Stage Information', {
            'fields': ('name', 'pipeline', 'description', 'stage_type')
        }),
        ('Configuration', {
            'fields': (
                ('order', 'default_probability'),
                ('is_active', 'auto_advance'),
                'required_fields'
            )
        }),
        ('Actions', {
            'fields': (
                'entry_criteria', 'exit_criteria',
                'automation_rules', 'notification_settings'
            ),
            'classes': ('collapse',)
        })
    )
    
    def get_queryset(self, request):
        """Add performance annotations"""
        return super().get_queryset(request).select_related(
            'pipeline'
        ).annotate(
            stage_opportunity_count=Count('opportunities'),
            stage_total_value=Sum('opportunities__amount')
        )
    
    def opportunity_count(self, obj):
        """Display opportunity count in this stage"""
        return obj.stage_opportunity_count
    
    opportunity_count.short_description = 'Opportunities'
    opportunity_count.admin_order_field = 'stage_opportunity_count'
    
    def total_value(self, obj):
        """Display total value in this stage"""
        if obj.stage_total_value:
            return format_html('${:,.2f}', obj.stage_total_value)
        return '$0.00'
    
    total_value.short_description = 'Total Value'
    total_value.admin_order_field = 'stage_total_value'
    
    def avg_age(self, obj):
        """Calculate average age of opportunities in this stage"""
        from django.db.models import Avg, ExpressionWrapper, DateTimeField
        from django.db.models.functions import Now
        
        avg_age = obj.opportunities.aggregate(
            avg_age=Avg(
                ExpressionWrapper(
                    Now() - F('updated_at'),
                    output_field=DateTimeField()
                )
            )
        )['avg_age']
        
        if avg_age:
            days = avg_age.days
            if days < 7:
                return format_html('<span style="color: green;">{} days</span>', days)
            elif days < 30:
                return format_html('<span style="color: orange;">{} days</span>', days)
            else:
                return format_html('<span style="color: red;">{} days</span>', days)
        
        return 'No data'
    
    avg_age.short_description = 'Avg Age'