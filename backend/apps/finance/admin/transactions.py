"""
Finance Transactions Admin
Admin interface for journal entries, invoices, bills, and payments
"""

from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.db.models import Sum, Count
from django.utils import timezone
from decimal import Decimal

from ..models import (
    JournalEntry, JournalEntryLine, Invoice, InvoiceItem,
    Bill, BillItem, Payment, PaymentApplication
)


@admin.register(JournalEntry)
class JournalEntryAdmin(admin.ModelAdmin):
    """Admin for journal entries"""
    list_display = [
        'entry_number', 'entry_date', 'reference', 'status',
        'total_debit', 'total_credit', 'difference', 'created_by', 'tenant'
    ]
    list_filter = [
        'status', 'entry_date', 'entry_type', 'tenant',
        ('created_by', admin.RelatedOnlyFieldFilter)
    ]
    search_fields = ['entry_number', 'reference', 'description']
    readonly_fields = ['entry_number', 'total_debit', 'total_credit', 'difference']
    date_hierarchy = 'entry_date'
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('tenant', 'entry_number', 'entry_date', 'entry_type', 'status')
        }),
        ('Details', {
            'fields': ('reference', 'reference_type', 'reference_id', 'description')
        }),
        ('Financial', {
            'fields': ('total_debit', 'total_credit', 'difference'),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('created_by', 'posted_by', 'posted_date', 'notes'),
            'classes': ('collapse',)
        })
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('tenant', 'created_by', 'posted_by')
    
    def difference(self, obj):
        """Calculate and display difference"""
        diff = obj.total_debit - obj.total_credit
        if abs(diff) <= Decimal('0.01'):
            return format_html('<span style="color: green;">✓ Balanced</span>')
        else:
            return format_html('<span style="color: red;">⚠ {}</span>', diff)
    difference.short_description = 'Balance'
    
    def save_model(self, request, obj, form, change):
        if not change:  # New object
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(JournalEntryLine)
class JournalEntryLineAdmin(admin.ModelAdmin):
    """Admin for journal entry lines"""
    list_display = [
        'journal_entry', 'account', 'debit_amount', 'credit_amount',
        'description', 'tenant'
    ]
    list_filter = [
        'account__account_type', 'tenant',
        ('journal_entry__entry_date', admin.DateFieldListFilter)
    ]
    search_fields = ['description', 'account__name', 'journal_entry__entry_number']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('tenant', 'journal_entry', 'account')
        }),
        ('Amounts', {
            'fields': ('debit_amount', 'credit_amount', 'description')
        }),
        ('Currency', {
            'fields': ('currency', 'exchange_rate', 'foreign_currency_amount'),
            'classes': ('collapse',)
        })
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'tenant', 'journal_entry', 'account'
        )


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    """Admin for customer invoices"""
    list_display = [
        'invoice_number', 'customer', 'invoice_date', 'due_date',
        'total_amount', 'amount_paid', 'amount_due', 'status', 'tenant'
    ]
    list_filter = [
        'status', 'invoice_date', 'due_date', 'customer__customer_type', 'tenant'
    ]
    search_fields = ['invoice_number', 'customer__name', 'reference']
    readonly_fields = ['invoice_number', 'total_amount', 'amount_paid', 'amount_due']
    date_hierarchy = 'invoice_date'
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('tenant', 'invoice_number', 'customer', 'invoice_date', 'due_date')
        }),
        ('Details', {
            'fields': ('reference', 'description', 'status', 'notes')
        }),
        ('Financial', {
            'fields': ('subtotal', 'tax_amount', 'total_amount', 'amount_paid', 'amount_due'),
            'classes': ('collapse',)
        }),
        ('Tax & Terms', {
            'fields': ('tax_group', 'payment_terms', 'currency'),
            'classes': ('collapse',)
        })
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'tenant', 'customer', 'tax_group', 'currency'
        )
    
    def amount_due(self, obj):
        """Display amount due with color coding"""
        if obj.amount_due <= 0:
            return format_html('<span style="color: green;">{}</span>', obj.amount_due)
        elif obj.amount_due > 0 and obj.due_date < timezone.now().date():
            return format_html('<span style="color: red;">{} (Overdue)</span>', obj.amount_due)
        else:
            return obj.amount_due
    amount_due.short_description = 'Amount Due'


@admin.register(InvoiceItem)
class InvoiceItemAdmin(admin.ModelAdmin):
    """Admin for invoice items"""
    list_display = [
        'invoice', 'description', 'quantity', 'unit_price',
        'total_amount', 'tenant'
    ]
    list_filter = ['tenant', ('invoice__invoice_date', admin.DateFieldListFilter)]
    search_fields = ['description', 'invoice__invoice_number']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('tenant', 'invoice', 'description')
        }),
        ('Pricing', {
            'fields': ('quantity', 'unit_price', 'total_amount')
        }),
        ('Tax & Account', {
            'fields': ('tax_rate', 'account'),
            'classes': ('collapse',)
        })
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('tenant', 'invoice', 'account')


@admin.register(Bill)
class BillAdmin(admin.ModelAdmin):
    """Admin for vendor bills"""
    list_display = [
        'bill_number', 'vendor', 'bill_date', 'due_date',
        'total_amount', 'amount_paid', 'amount_due', 'status', 'tenant'
    ]
    list_filter = [
        'status', 'bill_date', 'due_date', 'vendor__vendor_type', 'tenant'
    ]
    search_fields = ['bill_number', 'vendor__name', 'reference']
    readonly_fields = ['bill_number', 'total_amount', 'amount_paid', 'amount_due']
    date_hierarchy = 'bill_date'
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('tenant', 'bill_number', 'vendor', 'bill_date', 'due_date')
        }),
        ('Details', {
            'fields': ('reference', 'description', 'status', 'notes')
        }),
        ('Financial', {
            'fields': ('subtotal', 'tax_amount', 'total_amount', 'amount_paid', 'amount_due'),
            'classes': ('collapse',)
        }),
        ('Tax & Terms', {
            'fields': ('tax_group', 'payment_terms', 'currency'),
            'classes': ('collapse',)
        })
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'tenant', 'vendor', 'tax_group', 'currency'
        )
    
    def amount_due(self, obj):
        """Display amount due with color coding"""
        if obj.amount_due <= 0:
            return format_html('<span style="color: green;">{}</span>', obj.amount_due)
        elif obj.amount_due > 0 and obj.due_date < timezone.now().date():
            return format_html('<span style="color: red;">{} (Overdue)</span>', obj.amount_due)
        else:
            return obj.amount_due
    amount_due.short_description = 'Amount Due'


@admin.register(BillItem)
class BillItemAdmin(admin.ModelAdmin):
    """Admin for bill items"""
    list_display = [
        'bill', 'description', 'quantity', 'unit_price',
        'total_amount', 'tenant'
    ]
    list_filter = ['tenant', ('bill__bill_date', admin.DateFieldListFilter)]
    search_fields = ['description', 'bill__bill_number']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('tenant', 'bill', 'description')
        }),
        ('Pricing', {
            'fields': ('quantity', 'unit_price', 'total_amount')
        }),
        ('Tax & Account', {
            'fields': ('tax_rate', 'account'),
            'classes': ('collapse',)
        })
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('tenant', 'bill', 'account')


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    """Admin for payments"""
    list_display = [
        'payment_number', 'payment_type', 'entity_name', 'payment_date',
        'amount', 'status', 'payment_method', 'tenant'
    ]
    list_filter = [
        'payment_type', 'status', 'payment_date', 'payment_method', 'tenant'
    ]
    search_fields = ['payment_number', 'reference', 'customer__name', 'vendor__name']
    readonly_fields = ['payment_number']
    date_hierarchy = 'payment_date'
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('tenant', 'payment_number', 'payment_type', 'payment_date')
        }),
        ('Entity', {
            'fields': ('customer', 'vendor')
        }),
        ('Financial', {
            'fields': ('base_currency_amount', 'currency', 'exchange_rate', 'foreign_currency_amount')
        }),
        ('Details', {
            'fields': ('payment_method', 'reference', 'status', 'notes')
        }),
        ('Banking', {
            'fields': ('bank_account', 'cleared_date'),
            'classes': ('collapse',)
        })
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'tenant', 'customer', 'vendor', 'payment_method', 'bank_account', 'currency'
        )
    
    def entity_name(self, obj):
        """Display customer or vendor name"""
        if obj.customer:
            return f"Customer: {obj.customer.name}"
        elif obj.vendor:
            return f"Vendor: {obj.vendor.name}"
        return "N/A"
    entity_name.short_description = 'Entity'
    
    def amount(self, obj):
        """Display amount with currency"""
        return f"{obj.base_currency_amount} {obj.currency.code if obj.currency else 'USD'}"
    amount.short_description = 'Amount'


@admin.register(PaymentApplication)
class PaymentApplicationAdmin(admin.ModelAdmin):
    """Admin for payment applications"""
    list_display = [
        'payment', 'document_type', 'document_reference', 'amount_applied',
        'tenant'
    ]
    list_filter = ['document_type', 'tenant', ('payment__payment_date', admin.DateFieldListFilter)]
    search_fields = ['payment__payment_number', 'document_reference']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('tenant', 'payment', 'document_type')
        }),
        ('Application', {
            'fields': ('invoice', 'bill', 'amount_applied', 'notes')
        })
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'tenant', 'payment', 'invoice', 'bill'
        )
    
    def document_reference(self, obj):
        """Display document reference"""
        if obj.invoice:
            return f"Invoice: {obj.invoice.invoice_number}"
        elif obj.bill:
            return f"Bill: {obj.bill.bill_number}"
        return "N/A"
    document_reference.short_description = 'Document Reference'


# Custom admin actions
@admin.action(description="Mark selected invoices as sent")
def mark_invoices_as_sent(modeladmin, request, queryset):
    """Mark selected invoices as sent"""
    updated = queryset.update(status='SENT')
    modeladmin.message_user(request, f'{updated} invoices marked as sent.')


@admin.action(description="Mark selected bills as approved")
def mark_bills_as_approved(modeladmin, request, queryset):
    """Mark selected bills as approved"""
    updated = queryset.update(status='APPROVED')
    modeladmin.message_user(request, f'{updated} bills marked as approved.')


@admin.action(description="Mark selected payments as cleared")
def mark_payments_as_cleared(modeladmin, request, queryset):
    """Mark selected payments as cleared"""
    updated = queryset.update(status='CLEARED', cleared_date=timezone.now())
    modeladmin.message_user(request, f'{updated} payments marked as cleared.')


# Add actions to admin classes
InvoiceAdmin.actions = [mark_invoices_as_sent]
BillAdmin.actions = [mark_bills_as_approved]
PaymentAdmin.actions = [mark_payments_as_cleared]
