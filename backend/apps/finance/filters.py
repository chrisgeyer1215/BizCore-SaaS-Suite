# backend/apps/finance/filters.py

"""
Finance Module Filters
Custom filters for enhanced API querying
"""

import django_filters
from django.db.models import Q
from datetime import date, timedelta
from .models import (
    Account, JournalEntry, Invoice, Payment, Vendor, Bill,
    BankTransaction, BankReconciliation
)

class AccountFilter(django_filters.FilterSet):
    """Filter for Chart of Accounts"""
    
    account_type = django_filters.ChoiceFilter(choices=Account.ACCOUNT_TYPES)
    is_active = django_filters.BooleanFilter()
    is_bank_account = django_filters.BooleanFilter()
    is_cash_account = django_filters.BooleanFilter()
    has_balance = django_filters.BooleanFilter(method='filter_has_balance')
    balance_gt = django_filters.NumberFilter(field_name='current_balance', lookup_expr='gt')
    balance_lt = django_filters.NumberFilter(field_name='current_balance', lookup_expr='lt')
    parent_account = django_filters.ModelChoiceFilter(queryset=Account.objects.all())
    
    # Search filters
    search = django_filters.CharFilter(method='filter_search')
    
    class Meta:
        model = Account
        fields = [
            'account_type', 'category', 'is_active', 'is_bank_account',
            'is_cash_account', 'parent_account', 'currency'
        ]
    
    def filter_has_balance(self, queryset, name, value):
        """Filter accounts with non-zero balance"""
        if value:
            return queryset.exclude(current_balance=0)
        return queryset.filter(current_balance=0)
    
    def filter_search(self, queryset, name, value):
        """Search across multiple fields"""
        return queryset.filter(
            Q(code__icontains=value) |
            Q(name__icontains=value) |
            Q(description__icontains=value)
        )


class JournalEntryFilter(django_filters.FilterSet):
    """Filter for Journal Entries"""
    
    status = django_filters.ChoiceFilter(choices=JournalEntry.STATUS_CHOICES)
    entry_type = django_filters.ChoiceFilter(choices=JournalEntry.ENTRY_TYPE_CHOICES)
    entry_date = django_filters.DateFromToRangeFilter()
    created_at = django_filters.DateFromToRangeFilter()
    
    # Amount filters
    total_debit_gt = django_filters.NumberFilter(field_name='total_debit', lookup_expr='gt')
    total_debit_lt = django_filters.NumberFilter(field_name='total_debit', lookup_expr='lt')
    
    # User filters
    created_by = django_filters.ModelChoiceFilter(queryset=None)  # Set in __init__
    posted_by = django_filters.ModelChoiceFilter(queryset=None)   # Set in __init__
    
    # Search filters
    search = django_filters.CharFilter(method='filter_search')
    
    # Period filters
    period = django_filters.ChoiceFilter(
        choices=[
            ('today', 'Today'),
            ('this_week', 'This Week'),
            ('this_month', 'This Month'),
            ('this_year', 'This Year'),
            ('last_30_days', 'Last 30 Days'),
        ],
        method='filter_period'
    )
    
    class Meta:
        model = JournalEntry
        fields = [
            'status', 'entry_type', 'currency', 'source_document_type',
            'financial_period'
        ]
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.request:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            tenant_users = User.objects.filter(
                memberships__tenant=self.request.tenant
            )
            self.filters['created_by'].queryset = tenant_users
            self.filters['posted_by'].queryset = tenant_users
    
    def filter_search(self, queryset, name, value):
        """Search across multiple fields"""
        return queryset.filter(
            Q(entry_number__icontains=value) |
            Q(description__icontains=value) |
            Q(reference_number__icontains=value) |
            Q(notes__icontains=value)
        )
    
    def filter_period(self, queryset, name, value):
        """Filter by predefined periods"""
        today = date.today()
        
        if value == 'today':
            return queryset.filter(entry_date=today)
        elif value == 'this_week':
            week_start = today - timedelta(days=today.weekday())
            return queryset.filter(entry_date__gte=week_start)
        elif value == 'this_month':
            month_start = today.replace(day=1)
            return queryset.filter(entry_date__gte=month_start)
        elif value == 'this_year':
            year_start = today.replace(month=1, day=1)
            return queryset.filter(entry_date__gte=year_start)
        elif value == 'last_30_days':
            start_date = today - timedelta(days=30)
            return queryset.filter(entry_date__gte=start_date)
        
        return queryset


class InvoiceFilter(django_filters.FilterSet):
    """Filter for Invoices"""
    
    status = django_filters.ChoiceFilter(choices=Invoice.STATUS_CHOICES)
    invoice_type = django_filters.ChoiceFilter(choices=Invoice.INVOICE_TYPE_CHOICES)
    customer = django_filters.ModelChoiceFilter(queryset=None)  # Set in __init__
    
    # Date filters
    invoice_date = django_filters.DateFromToRangeFilter()
    due_date = django_filters.DateFromToRangeFilter()
    created_at = django_filters.DateFromToRangeFilter()
    
    # Amount filters
    total_amount_gt = django_filters.NumberFilter(field_name='total_amount', lookup_expr='gt')
    total_amount_lt = django_filters.NumberFilter(field_name='total_amount', lookup_expr='lt')
    amount_due_gt = django_filters.NumberFilter(field_name='amount_due', lookup_expr='gt')
    
    # Status filters
    is_overdue = django_filters.BooleanFilter(method='filter_overdue')
    is_paid = django_filters.BooleanFilter(method='filter_paid')
    is_recurring = django_filters.BooleanFilter()
    
    # Search filters
    search = django_filters.CharFilter(method='filter_search')
    
    # Period filters
    period = django_filters.ChoiceFilter(
        choices=[
            ('current_month', 'Current Month'),
            ('last_month', 'Last Month'),
            ('current_quarter', 'Current Quarter'),
            ('current_year', 'Current Year'),
        ],
        method='filter_period'
    )
    
    class Meta:
        model = Invoice
        fields = [
            'status', 'invoice_type', 'currency', 'is_recurring'
        ]
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.request:
            from apps.crm.models import Customer
            customers = Customer.objects.filter(tenant=self.request.tenant)
            self.filters['customer'].queryset = customers
    
    def filter_search(self, queryset, name, value):
        """Search across multiple fields"""
        return queryset.filter(
            Q(invoice_number__icontains=value) |
            Q(customer__name__icontains=value) |
            Q(customer_email__icontains=value) |
            Q(reference_number__icontains=value) |
            Q(description__icontains=value)
        )
    
    def filter_overdue(self, queryset, name, value):
        """Filter overdue invoices"""
        if value:
            return queryset.filter(
                status__in=['OPEN', 'SENT', 'VIEWED'],
                due_date__lt=date.today()
            )
        return queryset.exclude(
            status__in=['OPEN', 'SENT', 'VIEWED'],
            due_date__lt=date.today()
        )
    
    def filter_paid(self, queryset, name, value):
        """Filter paid invoices"""
        if value:
            return queryset.filter(status='PAID')
        return queryset.exclude(status='PAID')
    
    def filter_period(self, queryset, name, value):
        """Filter by predefined periods"""
        today = date.today()
        
        if value == 'current_month':
            month_start = today.replace(day=1)
            return queryset.filter(invoice_date__gte=month_start)
        elif value == 'last_month':
            if today.month == 1:
                last_month_start = today.replace(year=today.year - 1, month=12, day=1)
                last_month_end = today.replace(day=1) - timedelta(days=1)
            else:
                last_month_start = today.replace(month=today.month - 1, day=1)
                last_month_end = today.replace(day=1) - timedelta(days=1)
            return queryset.filter(
                invoice_date__gte=last_month_start,
                invoice_date__lte=last_month_end
            )
        elif value == 'current_quarter':
            quarter_start = date(today.year, ((today.month - 1) // 3) * 3 + 1, 1)
            return queryset.filter(invoice_date__gte=quarter_start)
        elif value == 'current_year':
            year_start = today.replace(month=1, day=1)
            return queryset.filter(invoice_date__gte=year_start)
        
        return queryset


class PaymentFilter(django_filters.FilterSet):
    """Filter for Payments"""
    
    payment_type = django_filters.ChoiceFilter(choices=Payment.PAYMENT_TYPE_CHOICES)
    payment_method = django_filters.ChoiceFilter(choices=Payment.PAYMENT_METHOD_CHOICES)
    status = django_filters.ChoiceFilter(choices=Payment.STATUS_CHOICES)
    
    # Entity filters
    customer = django_filters.ModelChoiceFilter(queryset=None)  # Set in __init__
    vendor = django_filters.ModelChoiceFilter(queryset=None)    # Set in __init__
    
    # Date filters
    payment_date = django_filters.DateFromToRangeFilter()
    created_at = django_filters.DateFromToRangeFilter()
    
    # Amount filters
    amount_gt = django_filters.NumberFilter(field_name='amount', lookup_expr='gt')
    amount_lt = django_filters.NumberFilter(field_name='amount', lookup_expr='lt')
    
    # Status filters
    is_reconciled = django_filters.BooleanFilter(method='filter_reconciled')
    is_allocated = django_filters.BooleanFilter(method='filter_allocated')
    
    # Search filters
    search = django_filters.CharFilter(method='filter_search')
    
    class Meta:
        model = Payment
        fields = [
            'payment_type', 'payment_method', 'status', 'currency', 'bank_account'
        ]
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.request:
            from apps.crm.models import Customer
            from .models import Vendor
            
            customers = Customer.objects.filter(tenant=self.request.tenant)
            vendors = Vendor.objects.filter(tenant=self.request.tenant)
            
            self.filters['customer'].queryset = customers
            self.filters['vendor'].queryset = vendors
    
    def filter_search(self, queryset, name, value):
        """Search across multiple fields"""
        return queryset.filter(
            Q(payment_number__icontains=value) |
            Q(reference_number__icontains=value) |
            Q(external_transaction_id__icontains=value) |
            Q(customer__name__icontains=value) |
            Q(vendor__company_name__icontains=value) |
            Q(description__icontains=value)
        )
    
    def filter_reconciled(self, queryset, name, value):
        """Filter reconciled payments"""
        if value:
            return queryset.exclude(reconciled_date__isnull=True)
        return queryset.filter(reconciled_date__isnull=True)
    
    def filter_allocated(self, queryset, name, value):
        """Filter allocated payments"""
        if value:
            return queryset.filter(applications__isnull=False).distinct()
        return queryset.filter(applications__isnull=True)


class VendorFilter(django_filters.FilterSet):
    """Filter for Vendors"""
    
    vendor_type = django_filters.ChoiceFilter(choices=Vendor.VENDOR_TYPE_CHOICES)
    status = django_filters.ChoiceFilter(choices=Vendor.STATUS_CHOICES)
    payment_terms = django_filters.ChoiceFilter(choices=Vendor.PAYMENT_TERMS_CHOICES)
    
    # Boolean filters
    is_inventory_supplier = django_filters.BooleanFilter()
    is_tax_exempt = django_filters.BooleanFilter()
    is_1099_vendor = django_filters.BooleanFilter()
    
    # Balance filters
    current_balance_gt = django_filters.NumberFilter(field_name='current_balance', lookup_expr='gt')
    credit_limit_gt = django_filters.NumberFilter(field_name='credit_limit', lookup_expr='gt')
    
    # Search filters
    search = django_filters.CharFilter(method='filter_search')
    
    class Meta:
        model = Vendor
        fields = [
            'vendor_type', 'status', 'payment_terms', 'currency',
            'is_inventory_supplier', 'is_tax_exempt', 'is_1099_vendor'
        ]
    
    def filter_search(self, queryset, name, value):
        """Search across multiple fields"""
        return queryset.filter(
            Q(vendor_number__icontains=value) |
            Q(company_name__icontains=value) |
            Q(display_name__icontains=value) |
            Q(email__icontains=value) |
            Q(primary_contact__icontains=value) |
            Q(supplier_code__icontains=value)
        )


class BillFilter(django_filters.FilterSet):
    """Filter for Bills"""
    
    status = django_filters.ChoiceFilter(choices=Bill.STATUS_CHOICES)
    bill_type = django_filters.ChoiceFilter(choices=Bill.BILL_TYPES)
    vendor = django_filters.ModelChoiceFilter(queryset=None)  # Set in __init__
    
    # Date filters
    bill_date = django_filters.DateFromToRangeFilter()
    due_date = django_filters.DateFromToRangeFilter()
    
    # Amount filters
    total_amount_gt = django_filters.NumberFilter(field_name='total_amount', lookup_expr='gt')
    total_amount_lt = django_filters.NumberFilter(field_name='total_amount', lookup_expr='lt')
    amount_due_gt = django_filters.NumberFilter(field_name='amount_due', lookup_expr='gt')
    
    # Status filters
    is_overdue = django_filters.BooleanFilter(method='filter_overdue')
    is_paid = django_filters.BooleanFilter(method='filter_paid')
    needs_approval = django_filters.BooleanFilter(method='filter_needs_approval')
    
    # Search filters
    search = django_filters.CharFilter(method='filter_search')
    
    class Meta:
        model = Bill
        fields = [
            'status', 'bill_type', 'currency', 'is_recurring'
        ]
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.request:
            vendors = Vendor.objects.filter(tenant=self.request.tenant)
            self.filters['vendor'].queryset = vendors
    
    def filter_search(self, queryset, name, value):
        """Search across multiple fields"""
        return queryset.filter(
            Q(bill_number__icontains=value) |
            Q(vendor_invoice_number__icontains=value) |
            Q(vendor__company_name__icontains=value) |
            Q(reference_number__icontains=value) |
            Q(description__icontains=value)
        )
    
    def filter_overdue(self, queryset, name, value):
        """Filter overdue bills"""
        if value:
            return queryset.filter(
                status__in=['OPEN', 'APPROVED'],
                due_date__lt=date.today()
            )
        return queryset.exclude(
            status__in=['OPEN', 'APPROVED'],
            due_date__lt=date.today()
        )
    
    def filter_paid(self, queryset, name, value):
        """Filter paid bills"""
        if value:
            return queryset.filter(status='PAID')
        return queryset.exclude(status='PAID')
    
    def filter_needs_approval(self, queryset, name, value):
        """Filter bills needing approval"""
        if value:
            return queryset.filter(status='PENDING_APPROVAL')
        return queryset.exclude(status='PENDING_APPROVAL')


class BankTransactionFilter(django_filters.FilterSet):
    """Filter for Bank Transactions"""
    
    transaction_type = django_filters.ChoiceFilter(choices=BankTransaction.TRANSACTION_TYPES)
    reconciliation_status = django_filters.ChoiceFilter(
        choices=BankTransaction.RECONCILIATION_STATUS_CHOICES
    )
    
    # Date filters
    transaction_date = django_filters.DateFromToRangeFilter()
    post_date = django_filters.DateFromToRangeFilter()
    
    # Amount filters
    amount_gt = django_filters.NumberFilter(field_name='amount', lookup_expr='gt')
    amount_lt = django_filters.NumberFilter(field_name='amount', lookup_expr='lt')
    
    # Status filters
    is_matched = django_filters.BooleanFilter(method='filter_matched')
    is_duplicate = django_filters.BooleanFilter()
    
    # Search filters
    search = django_filters.CharFilter(method='filter_search')
    
    class Meta:
        model = BankTransaction
        fields = [
            'bank_statement', 'transaction_type', 'reconciliation_status'
        ]
    
    def filter_search(self, queryset, name, value):
        """Search across multiple fields"""
        return queryset.filter(
            Q(description__icontains=value) |
            Q(memo__icontains=value) |
            Q(reference_number__icontains=value) |
            Q(payee__icontains=value) |
            Q(check_number__icontains=value)
        )
    
    def filter_matched(self, queryset, name, value):
        """Filter matched transactions"""
        if value:
            return queryset.filter(
                reconciliation_status__in=['MATCHED', 'MANUAL_MATCH', 'AUTO_MATCH']
            )
        return queryset.filter(reconciliation_status='UNMATCHED')


class BankReconciliationFilter(django_filters.FilterSet):
    """Filter for Bank Reconciliations"""
    
    status = django_filters.ChoiceFilter(choices=BankReconciliation.STATUS_CHOICES)
    is_balanced = django_filters.BooleanFilter()
    
    # Date filters
    reconciliation_date = django_filters.DateFromToRangeFilter()
    started_date = django_filters.DateFromToRangeFilter()
    completed_date = django_filters.DateFromToRangeFilter()
    
    # User filters
    started_by = django_filters.ModelChoiceFilter(queryset=None)    # Set in __init__
    completed_by = django_filters.ModelChoiceFilter(queryset=None)  # Set in __init__
    
    class Meta:
        model = BankReconciliation
        fields = [
            'bank_account', 'status', 'is_balanced'
        ]
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.request:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            tenant_users = User.objects.filter(
                memberships__tenant=self.request.tenant
            )
            self.filters['started_by'].queryset = tenant_users
            self.filters['completed_by'].queryset = tenant_users