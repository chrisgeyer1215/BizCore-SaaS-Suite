# backend/apps/finance/permissions.py

"""
Finance Module Permissions
Role-based access control for finance operations
"""

from rest_framework import permissions
from django.contrib.auth.models import Group
from apps.core.permissions import TenantPermission

class FinancePermission(TenantPermission):
    """Base finance permission class"""
    
    def has_permission(self, request, view):
        # First check tenant permission
        if not super().has_permission(request, view):
            return False
        
        # Check if user has finance module access
        if not request.user.has_perm('finance.view_finance_module'):
            return False
        
        return True


class FinanceManagerPermission(FinancePermission):
    """Permission for finance managers"""
    
    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        
        # Finance managers can access all finance operations
        return request.user.has_perm('finance.manage_finance') or \
               request.user.groups.filter(name='Finance Manager').exists()


class AccountingPermission(FinancePermission):
    """Permission for accounting operations"""
    
    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        
        # Check specific accounting permissions
        action = getattr(view, 'action', None)
        
        if action in ['create', 'update', 'partial_update', 'destroy']:
            return request.user.has_perm('finance.change_accounting_data')
        
        return request.user.has_perm('finance.view_accounting_data')


class JournalEntryPermission(FinancePermission):
    """Permission for journal entry operations"""
    
    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        
        action = getattr(view, 'action', None)
        
        if action == 'post_entry':
            return request.user.has_perm('finance.post_journal_entries')
        elif action == 'reverse_entry':
            return request.user.has_perm('finance.reverse_journal_entries')
        elif action in ['create', 'create_entry']:
            return request.user.has_perm('finance.create_journal_entries')
        elif action in ['update', 'partial_update']:
            return request.user.has_perm('finance.edit_journal_entries')
        
        return request.user.has_perm('finance.view_journal_entries')
    
    def has_object_permission(self, request, view, obj):
        """Object-level permissions for journal entries"""
        action = getattr(view, 'action', None)
        
        # Posted entries cannot be modified
        if obj.status == 'POSTED' and action in ['update', 'partial_update', 'destroy']:
            return False
        
        # Only entry creator or finance manager can modify draft entries
        if action in ['update', 'partial_update', 'destroy']:
            return obj.created_by == request.user or \
                   request.user.has_perm('finance.manage_finance')
        
        return True


class InvoicePermission(FinancePermission):
    """Permission for invoice operations"""
    
    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        
        action = getattr(view, 'action', None)
        
        if action == 'approve':
            return request.user.has_perm('finance.approve_invoices')
        elif action in ['send', 'send_invoices']:
            return request.user.has_perm('finance.send_invoices')
        elif action == 'void':
            return request.user.has_perm('finance.void_invoices')
        elif action in ['create', 'create_invoice']:
            return request.user.has_perm('finance.create_invoices')
        elif action in ['update', 'partial_update']:
            return request.user.has_perm('finance.edit_invoices')
        
        return request.user.has_perm('finance.view_invoices')
    
    def has_object_permission(self, request, view, obj):
        """Object-level permissions for invoices"""
        action = getattr(view, 'action', None)
        
        # Paid invoices cannot be modified
        if obj.status in ['PAID', 'VOIDED'] and action in ['update', 'partial_update', 'destroy']:
            return False
        
        # Check approval limits
        if action == 'approve' and obj.total_amount > 0:
            user_approval_limit = getattr(request.user, 'invoice_approval_limit', 0)
            if user_approval_limit and obj.total_amount > user_approval_limit:
                return False
        
        return True


class PaymentPermission(FinancePermission):
    """Permission for payment operations"""
    
    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        
        action = getattr(view, 'action', None)
        
        if action in ['create', 'create_payment']:
            return request.user.has_perm('finance.create_payments')
        elif action in ['apply_to_invoices', 'apply_to_bills']:
            return request.user.has_perm('finance.apply_payments')
        elif action == 'process_refund':
            return request.user.has_perm('finance.process_refunds')
        
        return request.user.has_perm('finance.view_payments')


class BankReconciliationPermission(FinancePermission):
    """Permission for bank reconciliation operations"""
    
    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        
        action = getattr(view, 'action', None)
        
        if action in ['start_reconciliation', 'complete']:
            return request.user.has_perm('finance.perform_bank_reconciliation')
        elif action == 'auto_match_transactions':
            return request.user.has_perm('finance.auto_match_bank_transactions')
        
        return request.user.has_perm('finance.view_bank_reconciliation')


class FinancialReportsPermission(FinancePermission):
    """Permission for financial reports"""
    
    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        
        action = getattr(view, 'action', None)
        
        # Different report types may have different permissions
        if action in ['balance_sheet', 'income_statement', 'cash_flow']:
            return request.user.has_perm('finance.view_financial_statements')
        elif action in ['ar_aging', 'ap_aging']:
            return request.user.has_perm('finance.view_aging_reports')
        elif action == 'trial_balance':
            return request.user.has_perm('finance.view_trial_balance')
        
        return request.user.has_perm('finance.view_financial_reports')


class VendorPermission(FinancePermission):
    """Permission for vendor operations"""
    
    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        
        action = getattr(view, 'action', None)
        
        if action in ['create', 'update', 'partial_update']:
            return request.user.has_perm('finance.manage_vendors')
        
        return request.user.has_perm('finance.view_vendors')


class BillPermission(FinancePermission):
    """Permission for bill operations"""
    
    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        
        action = getattr(view, 'action', None)
        
        if action == 'approve':
            return request.user.has_perm('finance.approve_bills')
        elif action in ['create', 'update', 'partial_update']:
            return request.user.has_perm('finance.manage_bills')
        
        return request.user.has_perm('finance.view_bills')
    
    def has_object_permission(self, request, view, obj):
        """Object-level permissions for bills"""
        action = getattr(view, 'action', None)
        
        # Paid bills cannot be modified
        if obj.status == 'PAID' and action in ['update', 'partial_update', 'destroy']:
            return False
        
        # Check approval limits
        if action == 'approve' and obj.total_amount > 0:
            user_approval_limit = getattr(request.user, 'bill_approval_limit', 0)
            if user_approval_limit and obj.total_amount > user_approval_limit:
                return False
        
        return True