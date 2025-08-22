"""
Bank Reconciliation Views
Handle bank account reconciliation and transaction matching
"""

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q, Sum
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from decimal import Decimal
import json

from apps.core.decorators import tenant_required
from ..models import (
    BankAccount, BankStatement, BankTransaction, BankReconciliation,
    ReconciliationAdjustment, ReconciliationRule, ReconciliationLog
)
from ..forms.bank_reconciliation import (
    BankReconciliationForm, ReconciliationAdjustmentForm,
    BankTransactionForm, ReconciliationRuleForm
)
from ..services.bank_reconciliation import BankReconciliationService


@login_required
@tenant_required
def bank_reconciliation_list(request):
    """List all bank reconciliations"""
    reconciliations = BankReconciliation.objects.filter(
        tenant=request.tenant
    ).select_related('bank_account').order_by('-reconciliation_date')
    
    # Filtering
    status = request.GET.get('status')
    bank_account_id = request.GET.get('bank_account')
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    
    if status:
        reconciliations = reconciliations.filter(status=status)
    if bank_account_id:
        reconciliations = reconciliations.filter(bank_account_id=bank_account_id)
    if date_from:
        reconciliations = reconciliations.filter(reconciliation_date__gte=date_from)
    if date_to:
        reconciliations = reconciliations.filter(reconciliation_date__lte=date_to)
    
    # Pagination
    paginator = Paginator(reconciliations, 25)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Summary stats
    total_reconciliations = reconciliations.count()
    completed_reconciliations = reconciliations.filter(status='COMPLETED').count()
    pending_reconciliations = reconciliations.filter(status='PENDING').count()
    
    context = {
        'page_obj': page_obj,
        'total_reconciliations': total_reconciliations,
        'completed_reconciliations': completed_reconciliations,
        'pending_reconciliations': pending_reconciliations,
        'bank_accounts': BankAccount.objects.filter(tenant=request.tenant, is_active=True),
        'status_choices': BankReconciliation.STATUS_CHOICES,
    }
    
    return render(request, 'finance/bank_reconciliation/list.html', context)


@login_required
@tenant_required
def bank_reconciliation_detail(request, reconciliation_id):
    """Show bank reconciliation details"""
    reconciliation = get_object_or_404(BankReconciliation, id=reconciliation_id, tenant=request.tenant)
    
    # Get reconciliation adjustments
    adjustments = reconciliation.adjustments.all().order_by('-created_at')
    
    # Get reconciliation logs
    logs = reconciliation.logs.all().order_by('-created_at')
    
    # Get unmatched transactions
    unmatched_transactions = BankTransaction.objects.filter(
        tenant=request.tenant,
        bank_account=reconciliation.bank_account,
        reconciliation__isnull=True,
        transaction_date__lte=reconciliation.reconciliation_date
    ).order_by('transaction_date')
    
    context = {
        'reconciliation': reconciliation,
        'adjustments': adjustments,
        'logs': logs,
        'unmatched_transactions': unmatched_transactions,
    }
    
    return render(request, 'finance/bank_reconciliation/detail.html', context)


@login_required
@tenant_required
def bank_reconciliation_create(request):
    """Create new bank reconciliation"""
    if request.method == 'POST':
        form = BankReconciliationForm(request.POST, tenant=request.tenant)
        
        if form.is_valid():
            reconciliation = form.save(commit=False)
            reconciliation.tenant = request.tenant
            reconciliation.created_by = request.user
            reconciliation.save()
            
            # Initialize reconciliation
            reconciliation_service = BankReconciliationService(request.tenant)
            reconciliation_service.initialize_reconciliation(reconciliation)
            
            messages.success(request, f'Bank reconciliation created successfully.')
            return redirect('finance:bank_reconciliation_detail', reconciliation_id=reconciliation.id)
    else:
        form = BankReconciliationForm(tenant=request.tenant)
    
    context = {
        'form': form,
        'bank_accounts': BankAccount.objects.filter(tenant=request.tenant, is_active=True),
    }
    
    return render(request, 'finance/bank_reconciliation/form.html', context)


@login_required
@tenant_required
def bank_reconciliation_edit(request, reconciliation_id):
    """Edit bank reconciliation"""
    reconciliation = get_object_or_404(BankReconciliation, id=reconciliation_id, tenant=request.tenant)
    
    if reconciliation.status in ['COMPLETED', 'LOCKED']:
        messages.error(request, 'Cannot edit completed or locked reconciliation.')
        return redirect('finance:bank_reconciliation_detail', reconciliation_id=reconciliation.id)
    
    if request.method == 'POST':
        form = BankReconciliationForm(request.POST, instance=reconciliation, tenant=request.tenant)
        
        if form.is_valid():
            form.save()
            messages.success(request, f'Bank reconciliation updated successfully.')
            return redirect('finance:bank_reconciliation_detail', reconciliation_id=reconciliation.id)
    else:
        form = BankReconciliationForm(instance=reconciliation, tenant=request.tenant)
    
    context = {
        'form': form,
        'reconciliation': reconciliation,
        'bank_accounts': BankAccount.objects.filter(tenant=request.tenant, is_active=True),
    }
    
    return render(request, 'finance/bank_reconciliation/form.html', context)


@login_required
@tenant_required
def bank_reconciliation_delete(request, reconciliation_id):
    """Delete bank reconciliation"""
    reconciliation = get_object_or_404(BankReconciliation, id=reconciliation_id, tenant=request.tenant)
    
    if reconciliation.status in ['COMPLETED', 'LOCKED']:
        messages.error(request, 'Cannot delete completed or locked reconciliation.')
        return redirect('finance:bank_reconciliation_detail', reconciliation_id=reconciliation.id)
    
    if request.method == 'POST':
        reconciliation.delete()
        messages.success(request, f'Bank reconciliation deleted successfully.')
        return redirect('finance:bank_reconciliation_list')
    
    context = {'reconciliation': reconciliation}
    return render(request, 'finance/bank_reconciliation/delete_confirm.html', context)


@login_required
@tenant_required
def reconciliation_workspace(request, reconciliation_id):
    """Main reconciliation workspace"""
    reconciliation = get_object_or_404(BankReconciliation, id=reconciliation_id, tenant=request.tenant)
    
    if reconciliation.status in ['COMPLETED', 'LOCKED']:
        messages.error(request, 'Cannot modify completed or locked reconciliation.')
        return redirect('finance:bank_reconciliation_detail', reconciliation_id=reconciliation.id)
    
    reconciliation_service = BankReconciliationService(request.tenant)
    
    # Get bank statement transactions
    bank_transactions = BankTransaction.objects.filter(
        tenant=request.tenant,
        bank_account=reconciliation.bank_account,
        transaction_date__lte=reconciliation.reconciliation_date
    ).order_by('transaction_date')
    
    # Get unmatched transactions
    unmatched_transactions = bank_transactions.filter(reconciliation__isnull=True)
    
    # Get matched transactions
    matched_transactions = bank_transactions.filter(reconciliation=reconciliation)
    
    # Get reconciliation summary
    summary = reconciliation_service.get_reconciliation_summary(reconciliation)
    
    context = {
        'reconciliation': reconciliation,
        'unmatched_transactions': unmatched_transactions,
        'matched_transactions': matched_transactions,
        'summary': summary,
        'reconciliation_rules': ReconciliationRule.objects.filter(
            tenant=request.tenant,
            bank_account=reconciliation.bank_account,
            is_active=True
        ),
    }
    
    return render(request, 'finance/bank_reconciliation/workspace.html', context)


@login_required
@tenant_required
def auto_reconcile_transactions(request, reconciliation_id):
    """Auto-reconcile transactions using rules"""
    reconciliation = get_object_or_404(BankReconciliation, id=reconciliation_id, tenant=request.tenant)
    
    if request.method == 'POST':
        try:
            reconciliation_service = BankReconciliationService(request.tenant)
            auto_matched_count = reconciliation_service.auto_reconcile_transactions(reconciliation)
            
            messages.success(request, f'{auto_matched_count} transactions auto-reconciled successfully.')
            return redirect('finance:reconciliation_workspace', reconciliation_id=reconciliation.id)
            
        except Exception as e:
            messages.error(request, f'Error auto-reconciling transactions: {str(e)}')
    
    return redirect('finance:reconciliation_workspace', reconciliation_id=reconciliation.id)


@login_required
@tenant_required
def match_transaction(request, reconciliation_id, transaction_id):
    """Manually match a bank transaction"""
    reconciliation = get_object_or_404(BankReconciliation, id=reconciliation_id, tenant=request.tenant)
    transaction = get_object_or_404(BankTransaction, id=transaction_id, tenant=request.tenant)
    
    if request.method == 'POST':
        # Handle transaction matching
        match_type = request.POST.get('match_type')
        matched_reference = request.POST.get('matched_reference')
        matched_amount = request.POST.get('matched_amount')
        
        try:
            reconciliation_service = BankReconciliationService(request.tenant)
            
            if match_type == 'manual':
                reconciliation_service.manually_match_transaction(
                    reconciliation, transaction, matched_reference, matched_amount
                )
            elif match_type == 'split':
                # Handle split matching
                pass
            
            messages.success(request, f'Transaction matched successfully.')
            return redirect('finance:reconciliation_workspace', reconciliation_id=reconciliation.id)
            
        except Exception as e:
            messages.error(request, f'Error matching transaction: {str(e)}')
    
    # Get potential matches
    reconciliation_service = BankReconciliationService(request.tenant)
    potential_matches = reconciliation_service.find_potential_matches(transaction)
    
    context = {
        'reconciliation': reconciliation,
        'transaction': transaction,
        'potential_matches': potential_matches,
    }
    
    return render(request, 'finance/bank_reconciliation/match_transaction.html', context)


@login_required
@tenant_required
def unmatch_transaction(request, reconciliation_id, transaction_id):
    """Unmatch a previously matched transaction"""
    reconciliation = get_object_or_404(BankReconciliation, id=reconciliation_id, tenant=request.tenant)
    transaction = get_object_or_404(BankTransaction, id=transaction_id, tenant=request.tenant)
    
    if request.method == 'POST':
        try:
            reconciliation_service = BankReconciliationService(request.tenant)
            reconciliation_service.unmatch_transaction(reconciliation, transaction)
            
            messages.success(request, f'Transaction unmatched successfully.')
            return redirect('finance:reconciliation_workspace', reconciliation_id=reconciliation.id)
            
        except Exception as e:
            messages.error(request, f'Error unmatching transaction: {str(e)}')
    
    context = {
        'reconciliation': reconciliation,
        'transaction': transaction,
    }
    
    return render(request, 'finance/bank_reconciliation/unmatch_transaction_confirm.html', context)


@login_required
@tenant_required
def add_adjustment(request, reconciliation_id):
    """Add reconciliation adjustment"""
    reconciliation = get_object_or_404(BankReconciliation, id=reconciliation_id, tenant=request.tenant)
    
    if request.method == 'POST':
        form = ReconciliationAdjustmentForm(request.POST)
        
        if form.is_valid():
            adjustment = form.save(commit=False)
            adjustment.reconciliation = reconciliation
            adjustment.created_by = request.user
            adjustment.save()
            
            messages.success(request, f'Adjustment added successfully.')
            return redirect('finance:reconciliation_workspace', reconciliation_id=reconciliation.id)
    else:
        form = ReconciliationAdjustmentForm()
    
    context = {
        'form': form,
        'reconciliation': reconciliation,
        'adjustment_types': ReconciliationAdjustment.ADJUSTMENT_TYPE_CHOICES,
    }
    
    return render(request, 'finance/bank_reconciliation/add_adjustment.html', context)


@login_required
@tenant_required
def edit_adjustment(request, reconciliation_id, adjustment_id):
    """Edit reconciliation adjustment"""
    reconciliation = get_object_or_404(BankReconciliation, id=reconciliation_id, tenant=request.tenant)
    adjustment = get_object_or_404(ReconciliationAdjustment, id=adjustment_id, reconciliation=reconciliation)
    
    if request.method == 'POST':
        form = ReconciliationAdjustmentForm(request.POST, instance=adjustment)
        
        if form.is_valid():
            form.save()
            messages.success(request, f'Adjustment updated successfully.')
            return redirect('finance:reconciliation_workspace', reconciliation_id=reconciliation.id)
    else:
        form = ReconciliationAdjustmentForm(instance=adjustment)
    
    context = {
        'form': form,
        'reconciliation': reconciliation,
        'adjustment': adjustment,
        'adjustment_types': ReconciliationAdjustment.ADJUSTMENT_TYPE_CHOICES,
    }
    
    return render(request, 'finance/bank_reconciliation/edit_adjustment.html', context)


@login_required
@tenant_required
def delete_adjustment(request, reconciliation_id, adjustment_id):
    """Delete reconciliation adjustment"""
    reconciliation = get_object_or_404(BankReconciliation, id=reconciliation_id, tenant=request.tenant)
    adjustment = get_object_or_404(ReconciliationAdjustment, id=adjustment_id, reconciliation=reconciliation)
    
    if request.method == 'POST':
        adjustment.delete()
        messages.success(request, f'Adjustment deleted successfully.')
        return redirect('finance:reconciliation_workspace', reconciliation_id=reconciliation.id)
    
    context = {
        'reconciliation': reconciliation,
        'adjustment': adjustment,
    }
    
    return render(request, 'finance/bank_reconciliation/delete_adjustment_confirm.html', context)


@login_required
@tenant_required
def complete_reconciliation(request, reconciliation_id):
    """Complete bank reconciliation"""
    reconciliation = get_object_or_404(BankReconciliation, id=reconciliation_id, tenant=request.tenant)
    
    if request.method == 'POST':
        try:
            reconciliation_service = BankReconciliationService(request.tenant)
            
            # Validate reconciliation
            validation_result = reconciliation_service.validate_reconciliation(reconciliation)
            if not validation_result['is_valid']:
                messages.error(request, f'Reconciliation cannot be completed: {", ".join(validation_result["errors"])}')
                return redirect('finance:reconciliation_workspace', reconciliation_id=reconciliation.id)
            
            # Complete reconciliation
            reconciliation_service.complete_reconciliation(reconciliation, request.user)
            
            messages.success(request, f'Bank reconciliation completed successfully.')
            return redirect('finance:bank_reconciliation_detail', reconciliation_id=reconciliation.id)
            
        except Exception as e:
            messages.error(request, f'Error completing reconciliation: {str(e)}')
    
    # Get final summary
    reconciliation_service = BankReconciliationService(request.tenant)
    summary = reconciliation_service.get_reconciliation_summary(reconciliation)
    
    context = {
        'reconciliation': reconciliation,
        'summary': summary,
    }
    
    return render(request, 'finance/bank_reconciliation/complete_confirm.html', context)


@login_required
@tenant_required
def reconciliation_rules(request):
    """Manage reconciliation rules"""
    rules = ReconciliationRule.objects.filter(tenant=request.tenant).select_related('bank_account').order_by('priority')
    
    context = {
        'rules': rules,
        'bank_accounts': BankAccount.objects.filter(tenant=request.tenant, is_active=True),
        'rule_types': ReconciliationRule.RULE_TYPE_CHOICES,
    }
    
    return render(request, 'finance/bank_reconciliation/rules.html', context)


@login_required
@tenant_required
def reconciliation_rule_create(request):
    """Create new reconciliation rule"""
    if request.method == 'POST':
        form = ReconciliationRuleForm(request.POST, tenant=request.tenant)
        
        if form.is_valid():
            rule = form.save(commit=False)
            rule.tenant = request.tenant
            rule.save()
            
            messages.success(request, f'Reconciliation rule created successfully.')
            return redirect('finance:reconciliation_rules')
    else:
        form = ReconciliationRuleForm(tenant=request.tenant)
    
    context = {
        'form': form,
        'action': 'Create',
        'bank_accounts': BankAccount.objects.filter(tenant=request.tenant, is_active=True),
        'rule_types': ReconciliationRule.RULE_TYPE_CHOICES,
    }
    
    return render(request, 'finance/bank_reconciliation/rule_form.html', context)


@login_required
@tenant_required
def reconciliation_rule_edit(request, rule_id):
    """Edit reconciliation rule"""
    rule = get_object_or_404(ReconciliationRule, id=rule_id, tenant=request.tenant)
    
    if request.method == 'POST':
        form = ReconciliationRuleForm(request.POST, instance=rule, tenant=request.tenant)
        
        if form.is_valid():
            form.save()
            messages.success(request, f'Reconciliation rule updated successfully.')
            return redirect('finance:reconciliation_rules')
    else:
        form = ReconciliationRuleForm(instance=rule, tenant=request.tenant)
    
    context = {
        'form': form,
        'rule': rule,
        'action': 'Edit',
        'bank_accounts': BankAccount.objects.filter(tenant=request.tenant, is_active=True),
        'rule_types': ReconciliationRule.RULE_TYPE_CHOICES,
    }
    
    return render(request, 'finance/bank_reconciliation/rule_form.html', context)


@login_required
@tenant_required
def reconciliation_rule_delete(request, rule_id):
    """Delete reconciliation rule"""
    rule = get_object_or_404(ReconciliationRule, id=rule_id, tenant=request.tenant)
    
    if request.method == 'POST':
        rule.delete()
        messages.success(request, f'Reconciliation rule deleted successfully.')
        return redirect('finance:reconciliation_rules')
    
    context = {'rule': rule}
    return render(request, 'finance/bank_reconciliation/rule_delete_confirm.html', context)


@login_required
@tenant_required
def import_bank_statement(request, reconciliation_id):
    """Import bank statement transactions"""
    reconciliation = get_object_or_404(BankReconciliation, id=reconciliation_id, tenant=request.tenant)
    
    if request.method == 'POST':
        if 'statement_file' in request.FILES:
            statement_file = request.FILES['statement_file']
            file_format = request.POST.get('file_format', 'csv')
            
            try:
                reconciliation_service = BankReconciliationService(request.tenant)
                import_result = reconciliation_service.import_bank_statement(
                    reconciliation, statement_file, file_format
                )
                
                if import_result['success']:
                    messages.success(request, f'{import_result["imported_count"]} transactions imported successfully.')
                    if import_result['errors']:
                        for error in import_result['errors']:
                            messages.warning(request, error)
                else:
                    messages.error(request, f'Import failed: {import_result["error"]}')
                    
            except Exception as e:
                messages.error(request, f'Error importing bank statement: {str(e)}')
        else:
            messages.error(request, 'Please select a file to import.')
    
    context = {
        'reconciliation': reconciliation,
        'supported_formats': ['csv', 'ofx', 'qif'],
    }
    
    return render(request, 'finance/bank_reconciliation/import_statement.html')


@login_required
@tenant_required
def export_reconciliation(request, reconciliation_id):
    """Export reconciliation report"""
    reconciliation = get_object_or_404(BankReconciliation, id=reconciliation_id, tenant=request.tenant)
    format_type = request.GET.get('format', 'pdf')
    
    try:
        reconciliation_service = BankReconciliationService(request.tenant)
        
        if format_type == 'csv':
            response = HttpResponse(content_type='text/csv')
            response['Content-Disposition'] = f'attachment; filename="reconciliation_{reconciliation.id}.csv"'
            
            import csv
            writer = csv.writer(response)
            writer.writerow([
                'Date', 'Description', 'Bank Amount', 'Book Amount', 'Difference', 'Status'
            ])
            
            # Export matched transactions
            matched_transactions = BankTransaction.objects.filter(
                reconciliation=reconciliation
            ).order_by('transaction_date')
            
            for transaction in matched_transactions:
                writer.writerow([
                    transaction.transaction_date,
                    transaction.description,
                    transaction.amount,
                    transaction.matched_amount or '',
                    transaction.amount - (transaction.matched_amount or Decimal('0.00')),
                    'Matched'
                ])
            
            # Export adjustments
            adjustments = reconciliation.adjustments.all().order_by('created_at')
            for adjustment in adjustments:
                writer.writerow([
                    adjustment.created_at.date(),
                    f"Adjustment: {adjustment.description}",
                    '',
                    adjustment.amount,
                    adjustment.amount,
                    'Adjustment'
                ])
            
            return response
        
        elif format_type == 'excel':
            # Excel export implementation
            pass
        
        else:  # PDF
            # PDF export implementation
            pass
        
    except Exception as e:
        messages.error(request, f'Error exporting reconciliation: {str(e)}')
        return redirect('finance:bank_reconciliation_detail', reconciliation_id=reconciliation.id)


# ============================================================================
# API ENDPOINTS FOR AJAX
# ============================================================================

@login_required
@tenant_required
def reconciliation_api_data(request, reconciliation_id):
    """API endpoint for reconciliation data (AJAX)"""
    try:
        reconciliation = get_object_or_404(BankReconciliation, id=reconciliation_id, tenant=request.tenant)
        
        # Get reconciliation summary
        reconciliation_service = BankReconciliationService(request.tenant)
        summary = reconciliation_service.get_reconciliation_summary(reconciliation)
        
        # Get unmatched transactions
        unmatched_transactions = BankTransaction.objects.filter(
            tenant=request.tenant,
            bank_account=reconciliation.bank_account,
            reconciliation__isnull=True,
            transaction_date__lte=reconciliation.reconciliation_date
        ).values('id', 'transaction_date', 'description', 'amount', 'reference')
        
        return JsonResponse({
            'summary': summary,
            'unmatched_transactions': list(unmatched_transactions)
        })
        
    except Exception as e:
        return JsonResponse({'error': str(e)})


@login_required
@tenant_required
def test_reconciliation_rule(request, rule_id):
    """Test reconciliation rule with sample data"""
    rule = get_object_or_404(ReconciliationRule, id=rule_id, tenant=request.tenant)
    
    if request.method == 'POST':
        test_data = request.POST.get('test_data', '')
        
        try:
            reconciliation_service = BankReconciliationService(request.tenant)
            test_result = reconciliation_service.test_reconciliation_rule(rule, test_data)
            
            return JsonResponse(test_result)
            
        except Exception as e:
            return JsonResponse({'error': str(e)})
    
    return JsonResponse({'error': 'Invalid request method'})
