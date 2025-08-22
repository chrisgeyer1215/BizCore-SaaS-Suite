"""
Finance Reconciliation Admin
Admin interface for bank reconciliation and related models
"""

from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.db.models import Sum, Count
from django.utils import timezone
from decimal import Decimal

from ..models import (
    BankAccount, BankStatement, BankTransaction, BankReconciliation,
    ReconciliationAdjustment, ReconciliationRule, ReconciliationLog
)


@admin.register(BankAccount)
class BankAccountAdmin(admin.ModelAdmin):
    """Admin for bank accounts"""
    list_display = [
        'account_number', 'bank_name', 'account_type', 'currency',
        'current_balance', 'status', 'tenant'
    ]
    list_filter = [
        'account_type', 'status', 'currency', 'tenant'
    ]
    search_fields = ['account_number', 'bank_name', 'account_name']
    readonly_fields = ['current_balance']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('tenant', 'account_number', 'bank_name', 'account_name')
        }),
        ('Account Details', {
            'fields': ('account_type', 'currency', 'current_balance', 'status')
        }),
        ('Banking Information', {
            'fields': ('routing_number', 'swift_code', 'iban'),
            'classes': ('collapse',)
        }),
        ('Settings', {
            'fields': ('auto_reconcile', 'reconciliation_frequency'),
            'classes': ('collapse',)
        })
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('tenant', 'currency')


@admin.register(BankStatement)
class BankStatementAdmin(admin.ModelAdmin):
    """Admin for bank statements"""
    list_display = [
        'bank_account', 'statement_date', 'opening_balance', 'closing_balance',
        'transaction_count', 'status', 'tenant'
    ]
    list_filter = [
        'status', 'statement_date', 'bank_account__bank_name', 'tenant'
    ]
    search_fields = ['bank_account__account_number', 'reference']
    readonly_fields = ['opening_balance', 'closing_balance', 'transaction_count']
    date_hierarchy = 'statement_date'
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('tenant', 'bank_account', 'statement_date', 'reference')
        }),
        ('Balances', {
            'fields': ('opening_balance', 'closing_balance', 'transaction_count')
        }),
        ('Status', {
            'fields': ('status', 'is_reconciled', 'reconciled_date')
        }),
        ('File Information', {
            'fields': ('statement_file', 'file_format', 'import_notes'),
            'classes': ('collapse',)
        })
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('tenant', 'bank_account')


@admin.register(BankTransaction)
class BankTransactionAdmin(admin.ModelAdmin):
    """Admin for bank transactions"""
    list_display = [
        'transaction_date', 'bank_account', 'description', 'amount',
        'balance', 'reconciliation_status', 'tenant'
    ]
    list_filter = [
        'transaction_date', 'bank_account__bank_name', 'transaction_type', 'tenant'
    ]
    search_fields = ['description', 'reference', 'bank_account__account_number']
    readonly_fields = ['balance', 'reconciliation_status']
    date_hierarchy = 'transaction_date'
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('tenant', 'bank_account', 'transaction_date', 'description')
        }),
        ('Financial', {
            'fields': ('amount', 'balance', 'transaction_type', 'reference')
        }),
        ('Reconciliation', {
            'fields': ('reconciliation', 'matched_amount', 'reconciliation_status')
        }),
        ('Additional Details', {
            'fields': ('check_number', 'memo', 'category'),
            'classes': ('collapse',)
        })
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'tenant', 'bank_account', 'reconciliation'
        )
    
    def reconciliation_status(self, obj):
        """Display reconciliation status with color coding"""
        if obj.reconciliation:
            return format_html('<span style="color: green;">✓ Reconciled</span>')
        elif obj.matched_amount and obj.matched_amount > 0:
            return format_html('<span style="color: orange;">⚠ Partially Matched</span>')
        else:
            return format_html('<span style="color: red;">✗ Unmatched</span>')
    reconciliation_status.short_description = 'Status'


@admin.register(BankReconciliation)
class BankReconciliationAdmin(admin.ModelAdmin):
    """Admin for bank reconciliations"""
    list_display = [
        'bank_account', 'reconciliation_date', 'book_balance', 'bank_balance',
        'difference', 'status', 'created_by', 'tenant'
    ]
    list_filter = [
        'status', 'reconciliation_date', 'bank_account__bank_name', 'tenant'
    ]
    search_fields = ['bank_account__account_number', 'notes']
    readonly_fields = ['book_balance', 'bank_balance', 'difference']
    date_hierarchy = 'reconciliation_date'
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('tenant', 'bank_account', 'reconciliation_date', 'status')
        }),
        ('Balances', {
            'fields': ('book_balance', 'bank_balance', 'difference')
        }),
        ('Details', {
            'fields': ('notes', 'created_by', 'created_date')
        }),
        ('Completion', {
            'fields': ('completed_by', 'completed_date', 'is_locked'),
            'classes': ('collapse',)
        })
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'tenant', 'bank_account', 'created_by', 'completed_by'
        )
    
    def difference(self, obj):
        """Display difference with color coding"""
        if abs(obj.difference) <= Decimal('0.01'):
            return format_html('<span style="color: green;">✓ Balanced</span>')
        else:
            return format_html('<span style="color: red;">⚠ {}</span>', obj.difference)
    difference.short_description = 'Difference'
    
    def save_model(self, request, obj, form, change):
        if not change:  # New object
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(ReconciliationAdjustment)
class ReconciliationAdjustmentAdmin(admin.ModelAdmin):
    """Admin for reconciliation adjustments"""
    list_display = [
        'reconciliation', 'adjustment_type', 'description', 'amount',
        'created_by', 'tenant'
    ]
    list_filter = [
        'adjustment_type', 'created_date', 'reconciliation__bank_account__bank_name', 'tenant'
    ]
    search_fields = ['description', 'reconciliation__bank_account__account_number']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('tenant', 'reconciliation', 'adjustment_type')
        }),
        ('Details', {
            'fields': ('description', 'amount', 'notes')
        }),
        ('Metadata', {
            'fields': ('created_by', 'created_date'),
            'classes': ('collapse',)
        })
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'tenant', 'reconciliation', 'created_by'
        )
    
    def save_model(self, request, obj, form, change):
        if not change:  # New object
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(ReconciliationRule)
class ReconciliationRuleAdmin(admin.ModelAdmin):
    """Admin for reconciliation rules"""
    list_display = [
        'name', 'bank_account', 'rule_type', 'priority', 'is_active', 'tenant'
    ]
    list_filter = [
        'rule_type', 'is_active', 'bank_account__bank_name', 'tenant'
    ]
    search_fields = ['name', 'description', 'bank_account__account_number']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('tenant', 'bank_account', 'name', 'description')
        }),
        ('Rule Configuration', {
            'fields': ('rule_type', 'priority', 'is_active')
        }),
        ('Matching Criteria', {
            'fields': ('description_pattern', 'amount_pattern', 'reference_pattern'),
            'classes': ('collapse',)
        }),
        ('Actions', {
            'fields': ('auto_match', 'auto_categorize', 'category'),
            'classes': ('collapse',)
        })
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('tenant', 'bank_account')


@admin.register(ReconciliationLog)
class ReconciliationLogAdmin(admin.ModelAdmin):
    """Admin for reconciliation logs"""
    list_display = [
        'reconciliation', 'action', 'description', 'created_by', 'created_date', 'tenant'
    ]
    list_filter = [
        'action', 'created_date', 'reconciliation__bank_account__bank_name', 'tenant'
    ]
    search_fields = ['description', 'reconciliation__bank_account__account_number']
    readonly_fields = ['created_date']
    date_hierarchy = 'created_date'
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('tenant', 'reconciliation', 'action', 'description')
        }),
        ('Details', {
            'fields': ('details', 'created_by', 'created_date')
        })
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'tenant', 'reconciliation', 'created_by'
        )
    
    def save_model(self, request, obj, form, change):
        if not change:  # New object
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


# Custom admin actions
@admin.action(description="Mark selected reconciliations as completed")
def mark_reconciliations_as_completed(modeladmin, request, queryset):
    """Mark selected reconciliations as completed"""
    updated = queryset.update(
        status='COMPLETED',
        completed_by=request.user,
        completed_date=timezone.now()
    )
    modeladmin.message_user(request, f'{updated} reconciliations marked as completed.')


@admin.action(description="Lock selected reconciliations")
def lock_reconciliations(modeladmin, request, queryset):
    """Lock selected reconciliations"""
    updated = queryset.update(is_locked=True)
    modeladmin.message_user(request, f'{updated} reconciliations locked.')


@admin.action(description="Unlock selected reconciliations")
def unlock_reconciliations(modeladmin, request, queryset):
    """Unlock selected reconciliations"""
    updated = queryset.update(is_locked=False)
    modeladmin.message_user(request, f'{updated} reconciliations unlocked.')


@admin.action(description="Activate selected reconciliation rules")
def activate_reconciliation_rules(modeladmin, request, queryset):
    """Activate selected reconciliation rules"""
    updated = queryset.update(is_active=True)
    modeladmin.message_user(request, f'{updated} reconciliation rules activated.')


@admin.action(description="Deactivate selected reconciliation rules")
def deactivate_reconciliation_rules(modeladmin, request, queryset):
    """Deactivate selected reconciliation rules"""
    updated = queryset.update(is_active=False)
    modeladmin.message_user(request, f'{updated} reconciliation rules deactivated.')


# Add actions to admin classes
BankReconciliationAdmin.actions = [mark_reconciliations_as_completed, lock_reconciliations, unlock_reconciliations]
ReconciliationRuleAdmin.actions = [activate_reconciliation_rules, deactivate_reconciliation_rules]
