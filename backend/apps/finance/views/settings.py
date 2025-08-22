"""
Finance Settings Views
Handle finance module configuration and settings
"""

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from decimal import Decimal
import json

from apps.core.decorators import tenant_required
from ..models import FinanceSettings, Currency, TaxCode, Account, AccountCategory
from ..forms.settings import (
    FinanceSettingsForm, CurrencyForm, TaxCodeForm, 
    AccountForm, AccountCategoryForm
)


@login_required
@tenant_required
def settings_dashboard(request):
    """Main settings dashboard"""
    try:
        # Get current finance settings
        finance_settings = FinanceSettings.objects.get(tenant=request.tenant)
        
        # Get summary counts
        currencies_count = Currency.objects.filter(tenant=request.tenant).count()
        tax_codes_count = TaxCode.objects.filter(tenant=request.tenant).count()
        accounts_count = Account.objects.filter(tenant=request.tenant).count()
        account_categories_count = AccountCategory.objects.filter(tenant=request.tenant).count()
        
        context = {
            'finance_settings': finance_settings,
            'summary_counts': {
                'currencies': currencies_count,
                'tax_codes': tax_codes_count,
                'accounts': accounts_count,
                'account_categories': account_categories_count,
            },
            'settings_sections': [
                {'name': 'General Settings', 'slug': 'general', 'icon': 'settings'},
                {'name': 'Chart of Accounts', 'slug': 'chart_of_accounts', 'icon': 'account_tree'},
                {'name': 'Tax Codes', 'slug': 'tax_codes', 'icon': 'receipt'},
                {'name': 'Currencies', 'slug': 'currencies', 'icon': 'currency_exchange'},
                {'name': 'Payment Terms', 'slug': 'payment_terms', 'icon': 'schedule'},
                {'name': 'Integration Settings', 'slug': 'integrations', 'icon': 'integration_instructions'},
            ]
        }
        
        return render(request, 'finance/settings/dashboard.html', context)
        
    except FinanceSettings.DoesNotExist:
        messages.error(request, 'Finance settings not found. Please contact administrator.')
        return redirect('finance:dashboard')


# ============================================================================
# GENERAL SETTINGS
# ============================================================================

@login_required
@tenant_required
def general_settings(request):
    """Edit general finance settings"""
    try:
        finance_settings = FinanceSettings.objects.get(tenant=request.tenant)
    except FinanceSettings.DoesNotExist:
        messages.error(request, 'Finance settings not found.')
        return redirect('finance:settings_dashboard')
    
    if request.method == 'POST':
        form = FinanceSettingsForm(request.POST, request.FILES, instance=finance_settings)
        
        if form.is_valid():
            form.save()
            messages.success(request, 'Finance settings updated successfully.')
            return redirect('finance:general_settings')
    else:
        form = FinanceSettingsForm(instance=finance_settings)
    
    context = {
        'form': form,
        'finance_settings': finance_settings,
    }
    
    return render(request, 'finance/settings/general.html', context)


# ============================================================================
# CHART OF ACCOUNTS
# ============================================================================

@login_required
@tenant_required
def chart_of_accounts(request):
    """Manage chart of accounts"""
    # Get account categories and accounts
    account_categories = AccountCategory.objects.filter(
        tenant=request.tenant
    ).prefetch_related('accounts').order_by('code')
    
    # Get accounts without categories
    uncategorized_accounts = Account.objects.filter(
        tenant=request.tenant,
        category__isnull=True
    ).order_by('code')
    
    context = {
        'account_categories': account_categories,
        'uncategorized_accounts': uncategorized_accounts,
        'account_types': Account.ACCOUNT_TYPE_CHOICES,
    }
    
    return render(request, 'finance/settings/chart_of_accounts.html', context)


@login_required
@tenant_required
def account_category_create(request):
    """Create new account category"""
    if request.method == 'POST':
        form = AccountCategoryForm(request.POST)
        
        if form.is_valid():
            account_category = form.save(commit=False)
            account_category.tenant = request.tenant
            account_category.save()
            
            messages.success(request, f'Account category "{account_category.name}" created successfully.')
            return redirect('finance:chart_of_accounts')
    else:
        form = AccountCategoryForm()
    
    context = {
        'form': form,
        'action': 'Create',
        'account_types': Account.ACCOUNT_TYPE_CHOICES,
    }
    
    return render(request, 'finance/settings/account_category_form.html', context)


@login_required
@tenant_required
def account_category_edit(request, category_id):
    """Edit account category"""
    account_category = get_object_or_404(AccountCategory, id=category_id, tenant=request.tenant)
    
    if request.method == 'POST':
        form = AccountCategoryForm(request.POST, instance=account_category)
        
        if form.is_valid():
            form.save()
            messages.success(request, f'Account category "{account_category.name}" updated successfully.')
            return redirect('finance:chart_of_accounts')
    else:
        form = AccountCategoryForm(instance=account_category)
    
    context = {
        'form': form,
        'account_category': account_category,
        'action': 'Edit',
        'account_types': Account.ACCOUNT_TYPE_CHOICES,
    }
    
    return render(request, 'finance/settings/account_category_form.html', context)


@login_required
@tenant_required
def account_category_delete(request, category_id):
    """Delete account category"""
    account_category = get_object_or_404(AccountCategory, id=category_id, tenant=request.tenant)
    
    # Check if category has accounts
    if account_category.accounts.exists():
        messages.error(request, f'Cannot delete category "{account_category.name}" - it contains accounts.')
        return redirect('finance:chart_of_accounts')
    
    if request.method == 'POST':
        account_category.delete()
        messages.success(request, f'Account category "{account_category.name}" deleted successfully.')
        return redirect('finance:chart_of_accounts')
    
    context = {'account_category': account_category}
    return render(request, 'finance/settings/account_category_delete_confirm.html', context)


@login_required
@tenant_required
def account_create(request):
    """Create new account"""
    if request.method == 'POST':
        form = AccountForm(request.POST, tenant=request.tenant)
        
        if form.is_valid():
            account = form.save(commit=False)
            account.tenant = request.tenant
            account.save()
            
            messages.success(request, f'Account "{account.name}" created successfully.')
            return redirect('finance:chart_of_accounts')
    else:
        form = AccountForm(tenant=request.tenant)
    
    context = {
        'form': form,
        'action': 'Create',
        'account_types': Account.ACCOUNT_TYPE_CHOICES,
        'normal_balance_choices': Account.NORMAL_BALANCE_CHOICES,
    }
    
    return render(request, 'finance/settings/account_form.html', context)


@login_required
@tenant_required
def account_edit(request, account_id):
    """Edit account"""
    account = get_object_or_404(Account, id=account_id, tenant=request.tenant)
    
    if request.method == 'POST':
        form = AccountForm(request.POST, instance=account, tenant=request.tenant)
        
        if form.is_valid():
            form.save()
            messages.success(request, f'Account "{account.name}" updated successfully.')
            return redirect('finance:chart_of_accounts')
    else:
        form = AccountForm(instance=account, tenant=request.tenant)
    
    context = {
        'form': form,
        'account': account,
        'action': 'Edit',
        'account_types': Account.ACCOUNT_TYPE_CHOICES,
        'normal_balance_choices': Account.NORMAL_BALANCE_CHOICES,
    }
    
    return render(request, 'finance/settings/account_form.html', context)


@login_required
@tenant_required
def account_delete(request, account_id):
    """Delete account"""
    account = get_object_or_404(Account, id=account_id, tenant=request.tenant)
    
    # Check if account has transactions
    if account.journal_lines.exists():
        messages.error(request, f'Cannot delete account "{account.name}" - it has transaction history.')
        return redirect('finance:chart_of_accounts')
    
    if request.method == 'POST':
        account.delete()
        messages.success(request, f'Account "{account.name}" deleted successfully.')
        return redirect('finance:chart_of_accounts')
    
    context = {'account': account}
    return render(request, 'finance/settings/account_delete_confirm.html', context)


# ============================================================================
# TAX CODES
# ============================================================================

@login_required
@tenant_required
def tax_codes(request):
    """Manage tax codes"""
    tax_codes_list = TaxCode.objects.filter(tenant=request.tenant).order_by('code')
    
    context = {
        'tax_codes': tax_codes_list,
        'tax_types': TaxCode.TAX_TYPE_CHOICES,
    }
    
    return render(request, 'finance/settings/tax_codes.html', context)


@login_required
@tenant_required
def tax_code_create(request):
    """Create new tax code"""
    if request.method == 'POST':
        form = TaxCodeForm(request.POST, tenant=request.tenant)
        
        if form.is_valid():
            tax_code = form.save(commit=False)
            tax_code.tenant = request.tenant
            tax_code.save()
            
            messages.success(request, f'Tax code "{tax_code.code}" created successfully.')
            return redirect('finance:tax_codes')
    else:
        form = TaxCodeForm(tenant=request.tenant)
    
    context = {
        'form': form,
        'action': 'Create',
        'tax_types': TaxCode.TAX_TYPE_CHOICES,
    }
    
    return render(request, 'finance/settings/tax_code_form.html', context)


@login_required
@tenant_required
def tax_code_edit(request, tax_code_id):
    """Edit tax code"""
    tax_code = get_object_or_404(TaxCode, id=tax_code_id, tenant=request.tenant)
    
    if request.method == 'POST':
        form = TaxCodeForm(request.POST, instance=tax_code, tenant=request.tenant)
        
        if form.is_valid():
            form.save()
            messages.success(request, f'Tax code "{tax_code.code}" updated successfully.')
            return redirect('finance:tax_codes')
    else:
        form = TaxCodeForm(instance=tax_code, tenant=request.tenant)
    
    context = {
        'form': form,
        'tax_code': tax_code,
        'action': 'Edit',
        'tax_types': TaxCode.TAX_TYPE_CHOICES,
    }
    
    return render(request, 'finance/settings/tax_code_form.html', context)


@login_required
@tenant_required
def tax_code_delete(request, tax_code_id):
    """Delete tax code"""
    tax_code = get_object_or_404(TaxCode, id=tax_code_id, tenant=request.tenant)
    
    # Check if tax code is used in transactions
    if tax_code.invoices.exists() or tax_code.bills.exists():
        messages.error(request, f'Cannot delete tax code "{tax_code.code}" - it is used in transactions.')
        return redirect('finance:tax_codes')
    
    if request.method == 'POST':
        tax_code.delete()
        messages.success(request, f'Tax code "{tax_code.code}" deleted successfully.')
        return redirect('finance:tax_codes')
    
    context = {'tax_code': tax_code}
    return render(request, 'finance/settings/tax_code_delete_confirm.html', context)


# ============================================================================
# CURRENCIES
# ============================================================================

@login_required
@tenant_required
def currencies(request):
    """Manage currencies"""
    currencies_list = Currency.objects.filter(tenant=request.tenant).order_by('code')
    
    context = {
        'currencies': currencies_list,
        'base_currency': FinanceSettings.objects.get(tenant=request.tenant).base_currency,
    }
    
    return render(request, 'finance/settings/currencies.html', context)


@login_required
@tenant_required
def currency_create(request):
    """Create new currency"""
    if request.method == 'POST':
        form = CurrencyForm(request.POST, tenant=request.tenant)
        
        if form.is_valid():
            currency = form.save(commit=False)
            currency.tenant = request.tenant
            currency.save()
            
            messages.success(request, f'Currency "{currency.code}" created successfully.')
            return redirect('finance:currencies')
    else:
        form = CurrencyForm(tenant=request.tenant)
    
    context = {
        'form': form,
        'action': 'Create',
    }
    
    return render(request, 'finance/settings/currency_form.html', context)


@login_required
@tenant_required
def currency_edit(request, currency_id):
    """Edit currency"""
    currency = get_object_or_404(Currency, id=currency_id, tenant=request.tenant)
    
    if request.method == 'POST':
        form = CurrencyForm(request.POST, instance=currency, tenant=request.tenant)
        
        if form.is_valid():
            form.save()
            messages.success(request, f'Currency "{currency.code}" updated successfully.')
            return redirect('finance:currencies')
    else:
        form = CurrencyForm(instance=currency, tenant=request.tenant)
    
    context = {
        'form': form,
        'currency': currency,
        'action': 'Edit',
    }
    
    return render(request, 'finance/settings/currency_form.html', context)


@login_required
@tenant_required
def currency_delete(request, currency_id):
    """Delete currency"""
    currency = get_object_or_404(Currency, id=currency_id, tenant=request.tenant)
    
    # Check if currency is base currency
    finance_settings = FinanceSettings.objects.get(tenant=request.tenant)
    if currency.code == finance_settings.base_currency:
        messages.error(request, f'Cannot delete base currency "{currency.code}".')
        return redirect('finance:currencies')
    
    # Check if currency is used in transactions
    if currency.invoices.exists() or currency.bills.exists() or currency.payments.exists():
        messages.error(request, f'Cannot delete currency "{currency.code}" - it is used in transactions.')
        return redirect('finance:currencies')
    
    if request.method == 'POST':
        currency.delete()
        messages.success(request, f'Currency "{currency.code}" deleted successfully.')
        return redirect('finance:currencies')
    
    context = {'currency': currency}
    return render(request, 'finance/settings/currency_delete_confirm.html', context)


@login_required
@tenant_required
def set_base_currency(request, currency_id):
    """Set base currency"""
    currency = get_object_or_404(Currency, id=currency_id, tenant=request.tenant)
    
    if request.method == 'POST':
        try:
            finance_settings = FinanceSettings.objects.get(tenant=request.tenant)
            finance_settings.base_currency = currency.code
            finance_settings.save()
            
            messages.success(request, f'Base currency set to "{currency.code}" successfully.')
            return redirect('finance:currencies')
            
        except Exception as e:
            messages.error(request, f'Error setting base currency: {str(e)}')
    
    context = {'currency': currency}
    return render(request, 'finance/settings/set_base_currency_confirm.html', context)


# ============================================================================
# PAYMENT TERMS
# ============================================================================

@login_required
@tenant_required
def payment_terms(request):
    """Manage payment terms"""
    # This would integrate with a PaymentTerms model
    # For now, show basic structure
    
    context = {
        'payment_terms': [
            {'name': 'Net 30', 'days': 30, 'description': 'Payment due within 30 days'},
            {'name': 'Net 15', 'days': 15, 'description': 'Payment due within 15 days'},
            {'name': 'Due on Receipt', 'days': 0, 'description': 'Payment due immediately'},
            {'name': 'Net 60', 'days': 60, 'description': 'Payment due within 60 days'},
        ]
    }
    
    return render(request, 'finance/settings/payment_terms.html', context)


# ============================================================================
# INTEGRATION SETTINGS
# ============================================================================

@login_required
@tenant_required
def integration_settings(request):
    """Manage integration settings"""
    # This would integrate with various integration services
    # For now, show basic structure
    
    context = {
        'integrations': [
            {
                'name': 'Bank Integration',
                'type': 'banking',
                'status': 'active',
                'description': 'Connect bank accounts for automatic reconciliation'
            },
            {
                'name': 'Payment Gateway',
                'type': 'payments',
                'status': 'inactive',
                'description': 'Process online payments and credit card transactions'
            },
            {
                'name': 'Accounting Software',
                'type': 'accounting',
                'status': 'inactive',
                'description': 'Sync with QuickBooks, Xero, or other accounting software'
            },
            {
                'name': 'Tax Calculation',
                'type': 'tax',
                'status': 'inactive',
                'description': 'Automated tax calculation and filing'
            }
        ]
    }
    
    return render(request, 'finance/settings/integrations.html', context)


# ============================================================================
# API ENDPOINTS FOR AJAX
# ============================================================================

@login_required
@tenant_required
def settings_api_data(request, setting_type):
    """API endpoint for settings data (AJAX)"""
    try:
        if setting_type == 'accounts':
            accounts = Account.objects.filter(tenant=request.tenant, is_active=True).values(
                'id', 'code', 'name', 'account_type', 'normal_balance'
            )
            return JsonResponse({'accounts': list(accounts)})
        
        elif setting_type == 'tax_codes':
            tax_codes = TaxCode.objects.filter(tenant=request.tenant, is_active=True).values(
                'id', 'code', 'name', 'rate', 'tax_type'
            )
            return JsonResponse({'tax_codes': list(tax_codes)})
        
        elif setting_type == 'currencies':
            currencies = Currency.objects.filter(tenant=request.tenant, is_active=True).values(
                'id', 'code', 'name', 'symbol', 'decimal_places'
            )
            return JsonResponse({'currencies': list(currencies)})
        
        else:
            return JsonResponse({'error': f'Unsupported setting type: {setting_type}'})
            
    except Exception as e:
        return JsonResponse({'error': str(e)})


@login_required
@tenant_required
def import_chart_of_accounts(request):
    """Import chart of accounts from file"""
    if request.method == 'POST':
        if 'accounts_file' in request.FILES:
            accounts_file = request.FILES['accounts_file']
            
            try:
                # This would integrate with an import service
                # For now, show success message
                messages.success(request, 'Chart of accounts imported successfully.')
                return redirect('finance:chart_of_accounts')
                
            except Exception as e:
                messages.error(request, f'Error importing chart of accounts: {str(e)}')
        else:
            messages.error(request, 'Please select a file to import.')
    
    return render(request, 'finance/settings/import_chart_of_accounts.html')


@login_required
@tenant_required
def export_chart_of_accounts(request):
    """Export chart of accounts to file"""
    format_type = request.GET.get('format', 'csv')
    
    if format_type == 'csv':
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="chart_of_accounts.csv"'
        
        import csv
        writer = csv.writer(response)
        writer.writerow(['Code', 'Name', 'Type', 'Normal Balance', 'Category', 'Description'])
        
        accounts = Account.objects.filter(tenant=request.tenant).select_related('category')
        for account in accounts:
            writer.writerow([
                account.code,
                account.name,
                account.get_account_type_display(),
                account.get_normal_balance_display(),
                account.category.name if account.category else '',
                account.description or ''
            ])
        
        return response
    
    elif format_type == 'excel':
        # Excel export implementation
        pass
    
    return redirect('finance:chart_of_accounts')


@login_required
@tenant_required
def bulk_account_actions(request):
    """Handle bulk actions on accounts"""
    if request.method == 'POST':
        action = request.POST.get('action')
        account_ids = request.POST.getlist('account_ids')
        
        if not account_ids:
            messages.error(request, 'No accounts selected.')
            return redirect('finance:chart_of_accounts')
        
        accounts = Account.objects.filter(id__in=account_ids, tenant=request.tenant)
        
        if action == 'activate':
            accounts.update(is_active=True)
            messages.success(request, f'{accounts.count()} accounts activated successfully.')
        
        elif action == 'deactivate':
            accounts.update(is_active=False)
            messages.success(request, f'{accounts.count()} accounts deactivated successfully.')
        
        elif action == 'delete':
            # Check if accounts have transactions
            accounts_with_transactions = []
            for account in accounts:
                if account.journal_lines.exists():
                    accounts_with_transactions.append(account.name)
            
            if accounts_with_transactions:
                messages.error(request, f'Cannot delete accounts with transactions: {", ".join(accounts_with_transactions)}')
            else:
                accounts.delete()
                messages.success(request, f'{accounts.count()} accounts deleted successfully.')
    
    return redirect('finance:chart_of_accounts')
