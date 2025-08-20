# backend/apps/finance/filters.py

"""
Finance Module Filters
DjangoFilter classes for API filtering
"""

import django_filters
from django.db.models import Q
from .models import (
    Account, JournalEntry, Invoice, Bill, Payment,
    Vendor, BankTransaction, BankReconciliation
)


class AccountFilter(django_filters.FilterSet):
    """Account filtering"""
    
    account_type = django_filters.CharFilter(field_name='account_type')
    is_active = django_filters.BooleanFilter(field_name='is_active')
    is_bank_account = django_filters.BooleanFilter(field_name='is_bank_account')
    parent_account = django_filters.NumberFilter(field_name='parent_account')
    category = django_filters.NumberFilter(field_name='category')
    search = django_filters.CharFilter(method='filter_search')
    
    class Meta:
        model = Account
        fields = ['account_type', 'is_active', 'is_bank_account', 'parent_account', 'category']
    
    def filter_search(self, queryset, name, value):
        return queryset.filter(
            Q(code__icontains=value) |
            Q(name__icontains=value) |
            Q(description__icontains=value)
        )


class JournalEntryFilter(django_filters.FilterSet):
    """Journal entry filtering"""
    
    status = django_filters.CharFilter(field_name='status')
    entry_type = django_filters.CharFilter(field_name='entry_type')
    entry_date_from = django_filters.DateFilter(field_name='entry_date', lookup_expr='gte')
    entry_date_to = django_filters.DateFilter(field_name='entry_date', lookup_expr='lte')
    amount_from = django_filters.NumberFilter(field_name='total_debit', lookup_expr='gte')
    amount_to = django_filters.NumberFilter(field_name='total_debit', lookup_expr='lte')
    created_by = django_filters.NumberFilter(field_name='created_by')
    
    class Meta:
        model = JournalEntry
        fields = ['status', 'entry_type', 'created_by']


class InvoiceFilter(django_filters.FilterSet):
    """Invoice filtering"""
    
    status = django_filters.CharFilter(field_name='status')
    invoice_type = django_filters.CharFilter(field_name='invoice_type')
    customer = django_filters.NumberFilter(field_name='customer')
    invoice_date_from = django_filters.DateFilter(field_name='invoice_date', lookup_expr='gte')
    invoice_date_to = django_filters.DateFilter(field_name='invoice_date', lookup_expr='lte')
    due_date_from = django_filters.DateFilter(field_name='due_date', lookup_expr='gte')
    due_date_to = django_filters.DateFilter(field_name='due_date', lookup_expr='lte')
    amount_from = django_filters.NumberFilter(field_name='total_amount', lookup_expr='gte')
    amount_to = django_filters.NumberFilter(field_name='total_amount', lookup_expr='lte')
    is_overdue = django_filters.BooleanFilter(method='filter_overdue')
    
    class Meta:
        model = Invoice
        fields = ['status', 'invoice_type', 'customer']
    
    def filter_overdue(self, queryset, name, value):
        from datetime import date
        if value:
            return queryset.filter(
                due_date__lt=date.today(),
                status__in=['OPEN', 'SENT', 'VIEWED', 'PARTIAL'],
                amount_due__gt=0
            )
        return queryset


class BillFilter(django_filters.FilterSet):
    """Bill filtering"""
    
    status = django_filters.CharFilter(field_name='status')
    bill_type = django_filters.CharFilter(field_name='bill_type')
    vendor = django_filters.NumberFilter(field_name='vendor')
    bill_date_from = django_filters.DateFilter(field_name='bill_date', lookup_expr='gte')
    bill_date_to = django_filters.DateFilter(field_name='bill_date', lookup_expr='lte')
    due_date_from = django_filters.DateFilter(field_name='due_date', lookup_expr='gte')
    due_date_to = django_filters.DateFilter(field_name='due_date', lookup_expr='lte')
    amount_from = django_filters.NumberFilter(field_name='total_amount', lookup_expr='gte')
    amount_to = django_filters.NumberFilter(field_name='total_amount', lookup_expr='lte')
    is_overdue = django_filters.BooleanFilter(method='filter_overdue')
    
    class Meta:
        model = Bill
        fields = ['status', 'bill_type', 'vendor']
    
    def filter_overdue(self, queryset, name, value):
        from datetime import date
        if value:
            return queryset.filter(
                due_date__lt=date.today(),
                status__in=['OPEN', 'APPROVED', 'PARTIAL'],
                amount_due__gt=0
            )
        return queryset


class PaymentFilter(django_filters.FilterSet):
    """Payment filtering"""
    
    payment_type = django_filters.CharFilter(field_name='payment_type')
    payment_method = django_filters.CharFilter(field_name='payment_method')
    status = django_filters.CharFilter(field_name='status')
    customer = django_filters.NumberFilter(field_name='customer')
    vendor = django_filters.NumberFilter(field_name='vendor')
    payment_date_from = django_filters.DateFilter(field_name='payment_date', lookup_expr='gte')
    payment_date_to = django_filters.DateFilter(field_name='payment_date', lookup_expr='lte')
    amount_from = django_filters.NumberFilter(field_name='amount', lookup_expr='gte')
    amount_to = django_filters.NumberFilter(field_name='amount', lookup_expr='lte')
    bank_account = django_filters.NumberFilter(field_name='bank_account')
    
    class Meta:
        model = Payment
        fields = ['payment_type', 'payment_method', 'status', 'customer', 'vendor', 'bank_account']


class VendorFilter(django_filters.FilterSet):
    """Vendor filtering"""
    
    status = django_filters.CharFilter(field_name='status')
    vendor_type = django_filters.CharFilter(field_name='vendor_type')
    is_inventory_supplier = django_filters.BooleanFilter(field_name='is_inventory_supplier')
    is_1099_vendor = django_filters.BooleanFilter(field_name='is_1099_vendor')
    payment_terms = django_filters.CharFilter(field_name='payment_terms')
    search = django_filters.CharFilter(method='filter_search')
    
    class Meta:
        model = Vendor
        fields = ['status', 'vendor_type', 'is_inventory_supplier', 'is_1099_vendor', 'payment_terms']
    
    def filter_search(self, queryset, name, value):
        return queryset.filter(
            Q(company_name__icontains=value) |
            Q(vendor_number__icontains=value) |
            Q(email__icontains=value)
        )


class BankTransactionFilter(django_filters.FilterSet):
    """Bank transaction filtering"""
    
    bank_statement = django_filters.NumberFilter(field_name='bank_statement')
    transaction_type = django_filters.CharFilter(field_name='transaction_type')
    reconciliation_status = django_filters.CharFilter(field_name='reconciliation_status')
    transaction_date_from = django_filters.DateFilter(field_name='transaction_date', lookup_expr='gte')
    transaction_date_to = django_filters.DateFilter(field_name='transaction_date', lookup_expr='lte')
    amount_from = django_filters.NumberFilter(field_name='amount', lookup_expr='gte')
    amount_to = django_filters.NumberFilter(field_name='amount', lookup_expr='lte')
    is_duplicate = django_filters.BooleanFilter(field_name='is_duplicate')
    
    class Meta:
        model = BankTransaction
        fields = ['bank_statement', 'transaction_type', 'reconciliation_status', 'is_duplicate']


class BankReconciliationFilter(django_filters.FilterSet):
    """Bank reconciliation filtering"""
    
    bank_account = django_filters.NumberFilter(field_name='bank_account')
    status = django_filters.CharFilter(field_name='status')
    reconciliation_date_from = django_filters.DateFilter(field_name='reconciliation_date', lookup_expr='gte')
    reconciliation_date_to = django_filters.DateFilter(field_name='reconciliation_date', lookup_expr='lte')
    is_balanced = django_filters.BooleanFilter(field_name='is_balanced')
    started_by = django_filters.NumberFilter(field_name='started_by')
    completed_by = django_filters.NumberFilter(field_name='completed_by')
    
    class Meta:
        model = BankReconciliation
        fields = ['bank_account', 'status', 'is_balanced', 'started_by', 'completed_by']