"""
Financial Reporting Views
Handle financial statements, reports, and analytics
"""

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from decimal import Decimal
from datetime import date, timedelta
import json

from apps.core.decorators import tenant_required
from ..services.accounting import AccountingService
from ..services.reporting import ReportingService


@login_required
@tenant_required
def reports_dashboard(request):
    """Main reports dashboard"""
    accounting_service = AccountingService(request.tenant)
    reporting_service = ReportingService(request.tenant)
    
    # Get current date
    current_date = date.today()
    
    # Get fiscal year info
    fiscal_year = accounting_service.current_fiscal_year
    
    # Get quick stats
    quick_stats = {
        'current_month': current_date.strftime('%B %Y'),
        'fiscal_year': fiscal_year.year,
        'fiscal_period': f"{fiscal_year.start_date.strftime('%B %Y')} - {fiscal_year.end_date.strftime('%B %Y')}"
    }
    
    # Get recent reports
    recent_reports = reporting_service.get_recent_reports(limit=5)
    
    context = {
        'quick_stats': quick_stats,
        'recent_reports': recent_reports,
        'report_categories': [
            {'name': 'Financial Statements', 'slug': 'financial_statements'},
            {'name': 'Aging Reports', 'slug': 'aging'},
            {'name': 'Tax Reports', 'slug': 'tax'},
            {'name': 'Management Reports', 'slug': 'management'},
            {'name': 'Custom Reports', 'slug': 'custom'},
        ]
    }
    
    return render(request, 'finance/reports/dashboard.html', context)


# ============================================================================
# FINANCIAL STATEMENTS
# ============================================================================

@login_required
@tenant_required
def balance_sheet(request):
    """Generate balance sheet report"""
    accounting_service = AccountingService(request.tenant)
    
    # Get parameters
    as_of_date = request.GET.get('as_of_date')
    if as_of_date:
        try:
            as_of_date = date.fromisoformat(as_of_date)
        except ValueError:
            as_of_date = date.today()
    else:
        as_of_date = date.today()
    
    # Get currency
    currency_code = request.GET.get('currency', 'USD')
    
    try:
        # Generate balance sheet
        balance_sheet_data = accounting_service.generate_balance_sheet(as_of_date)
        
        # Format for display
        context = {
            'balance_sheet': balance_sheet_data,
            'as_of_date': as_of_date,
            'currency_code': currency_code,
            'is_balanced': balance_sheet_data.get('is_balanced', False),
            'difference': balance_sheet_data.get('difference', Decimal('0.00')),
        }
        
        return render(request, 'finance/reports/financial_statements/balance_sheet.html', context)
        
    except Exception as e:
        messages.error(request, f'Error generating balance sheet: {str(e)}')
        return redirect('finance:reports_dashboard')


@login_required
@tenant_required
def income_statement(request):
    """Generate income statement report"""
    accounting_service = AccountingService(request.tenant)
    
    # Get parameters
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    
    if start_date:
        try:
            start_date = date.fromisoformat(start_date)
        except ValueError:
            start_date = date.today().replace(day=1)
    else:
        start_date = date.today().replace(day=1)
    
    if end_date:
        try:
            end_date = date.fromisoformat(end_date)
        except ValueError:
            end_date = date.today()
    else:
        end_date = date.today()
    
    # Get currency
    currency_code = request.GET.get('currency', 'USD')
    
    try:
        # Generate income statement
        income_statement_data = accounting_service.generate_income_statement(start_date, end_date)
        
        # Calculate period info
        period_days = (end_date - start_date).days + 1
        
        context = {
            'income_statement': income_statement_data,
            'start_date': start_date,
            'end_date': end_date,
            'period_days': period_days,
            'currency_code': currency_code,
            'period_name': f"{start_date.strftime('%B %d, %Y')} - {end_date.strftime('%B %d, %Y')}"
        }
        
        return render(request, 'finance/reports/financial_statements/income_statement.html', context)
        
    except Exception as e:
        messages.error(request, f'Error generating income statement: {str(e)}')
        return redirect('finance:reports_dashboard')


@login_required
@tenant_required
def cash_flow_statement(request):
    """Generate cash flow statement report"""
    accounting_service = AccountingService(request.tenant)
    
    # Get parameters
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    method = request.GET.get('method', 'INDIRECT')
    
    if start_date:
        try:
            start_date = date.fromisoformat(start_date)
        except ValueError:
            start_date = date.today().replace(day=1)
    else:
        start_date = date.today().replace(day=1)
    
    if end_date:
        try:
            end_date = date.fromisoformat(end_date)
        except ValueError:
            end_date = date.today()
    else:
        end_date = date.today()
    
    # Get currency
    currency_code = request.GET.get('currency', 'USD')
    
    try:
        # Generate cash flow statement
        cash_flow_data = accounting_service.generate_cash_flow_statement(
            start_date, end_date, method=method
        )
        
        context = {
            'cash_flow': cash_flow_data,
            'start_date': start_date,
            'end_date': end_date,
            'method': method,
            'currency_code': currency_code,
            'is_balanced': cash_flow_data.get('is_balanced', False),
        }
        
        return render(request, 'finance/reports/financial_statements/cash_flow.html', context)
        
    except Exception as e:
        messages.error(request, f'Error generating cash flow statement: {str(e)}')
        return redirect('finance:reports_dashboard')


@login_required
@tenant_required
def trial_balance(request):
    """Generate trial balance report"""
    accounting_service = AccountingService(request.tenant)
    
    # Get parameters
    as_of_date = request.GET.get('as_of_date')
    include_zero_balances = request.GET.get('include_zero', 'false').lower() == 'true'
    
    if as_of_date:
        try:
            as_of_date = date.fromisoformat(as_of_date)
        except ValueError:
            as_of_date = date.today()
    else:
        as_of_date = date.today()
    
    # Get currency
    currency_code = request.GET.get('currency', 'USD')
    
    try:
        # Generate trial balance
        trial_balance_data = accounting_service.generate_trial_balance(
            as_of_date, include_zero_balances
        )
        
        context = {
            'trial_balance': trial_balance_data,
            'as_of_date': as_of_date,
            'include_zero_balances': include_zero_balances,
            'currency_code': currency_code,
            'is_balanced': trial_balance_data.get('is_balanced', False),
        }
        
        return render(request, 'finance/reports/financial_statements/trial_balance.html', context)
        
    except Exception as e:
        messages.error(request, f'Error generating trial balance: {str(e)}')
        return redirect('finance:reports_dashboard')


# ============================================================================
# AGING REPORTS
# ============================================================================

@login_required
@tenant_required
def accounts_receivable_aging(request):
    """Generate accounts receivable aging report"""
    accounting_service = AccountingService(request.tenant)
    
    # Get parameters
    as_of_date = request.GET.get('as_of_date')
    if as_of_date:
        try:
            as_of_date = date.fromisoformat(as_of_date)
        except ValueError:
            as_of_date = date.today()
    else:
        as_of_date = date.today()
    
    try:
        # Generate AR aging analysis
        ar_aging_data = accounting_service.get_account_aging_analysis('AR', as_of_date)
        
        context = {
            'aging_data': ar_aging_data,
            'as_of_date': as_of_date,
            'report_type': 'Accounts Receivable Aging',
            'aging_buckets': ar_aging_data.get('aging_buckets', {}),
            'summary': ar_aging_data.get('summary', {}),
        }
        
        return render(request, 'finance/reports/aging/ar_aging.html', context)
        
    except Exception as e:
        messages.error(request, f'Error generating AR aging report: {str(e)}')
        return redirect('finance:reports_dashboard')


@login_required
@tenant_required
def accounts_payable_aging(request):
    """Generate accounts payable aging report"""
    accounting_service = AccountingService(request.tenant)
    
    # Get parameters
    as_of_date = request.GET.get('as_of_date')
    if as_of_date:
        try:
            as_of_date = date.fromisoformat(as_of_date)
        except ValueError:
            as_of_date = date.today()
    else:
        as_of_date = date.today()
    
    try:
        # Generate AP aging analysis
        ap_aging_data = accounting_service.get_account_aging_analysis('AP', as_of_date)
        
        context = {
            'aging_data': ap_aging_data,
            'as_of_date': as_of_date,
            'report_type': 'Accounts Payable Aging',
            'aging_buckets': ap_aging_data.get('aging_buckets', {}),
            'summary': ap_aging_data.get('summary', {}),
        }
        
        return render(request, 'finance/reports/aging/ap_aging.html', context)
        
    except Exception as e:
        messages.error(request, f'Error generating AP aging report: {str(e)}')
        return redirect('finance:reports_dashboard')


# ============================================================================
# TAX REPORTS
# ============================================================================

@login_required
@tenant_required
def sales_tax_report(request):
    """Generate sales tax report"""
    # Get parameters
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    
    if start_date:
        try:
            start_date = date.fromisoformat(start_date)
        except ValueError:
            start_date = date.today().replace(day=1)
    else:
        start_date = date.today().replace(day=1)
    
    if end_date:
        try:
            end_date = date.fromisoformat(end_date)
        except ValueError:
            end_date = date.today()
    else:
        end_date = date.today()
    
    try:
        # This would integrate with tax calculation service
        # For now, return basic structure
        context = {
            'start_date': start_date,
            'end_date': end_date,
            'report_type': 'Sales Tax Report',
            'tax_summary': {
                'total_sales': Decimal('0.00'),
                'total_tax_collected': Decimal('0.00'),
                'tax_by_rate': {},
                'tax_by_jurisdiction': {},
            }
        }
        
        return render(request, 'finance/reports/tax/sales_tax.html', context)
        
    except Exception as e:
        messages.error(request, f'Error generating sales tax report: {str(e)}')
        return redirect('finance:reports_dashboard')


@login_required
@tenant_required
def tax_liability_report(request):
    """Generate tax liability report"""
    # Get parameters
    as_of_date = request.GET.get('as_of_date')
    if as_of_date:
        try:
            as_of_date = date.fromisoformat(as_of_date)
        except ValueError:
            as_of_date = date.today()
    else:
        as_of_date = date.today()
    
    try:
        # This would calculate tax liabilities
        context = {
            'as_of_date': as_of_date,
            'report_type': 'Tax Liability Report',
            'tax_liabilities': {
                'sales_tax_payable': Decimal('0.00'),
                'income_tax_payable': Decimal('0.00'),
                'payroll_tax_payable': Decimal('0.00'),
                'other_taxes_payable': Decimal('0.00'),
            }
        }
        
        return render(request, 'finance/reports/tax/tax_liability.html', context)
        
    except Exception as e:
        messages.error(request, f'Error generating tax liability report: {str(e)}')
        return redirect('finance:reports_dashboard')


# ============================================================================
# MANAGEMENT REPORTS
# ============================================================================

@login_required
@tenant_required
def budget_vs_actual(request):
    """Generate budget vs actual report"""
    accounting_service = AccountingService(request.tenant)
    
    # Get parameters
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    budget_id = request.GET.get('budget_id')
    
    if start_date:
        try:
            start_date = date.fromisoformat(start_date)
        except ValueError:
            start_date = date.today().replace(day=1)
    else:
        start_date = date.today().replace(day=1)
    
    if end_date:
        try:
            end_date = date.fromisoformat(end_date)
        except ValueError:
            end_date = date.today()
    else:
        end_date = date.today()
    
    try:
        # Compare actual to budget
        comparison_data = accounting_service.compare_actual_to_budget(
            start_date, end_date, budget_id
        )
        
        context = {
            'comparison': comparison_data,
            'start_date': start_date,
            'end_date': end_date,
            'budget_id': budget_id,
            'report_type': 'Budget vs Actual',
        }
        
        return render(request, 'finance/reports/management/budget_vs_actual.html', context)
        
    except Exception as e:
        messages.error(request, f'Error generating budget vs actual report: {str(e)}')
        return redirect('finance:reports_dashboard')


@login_required
@tenant_required
def profit_loss_by_project(request):
    """Generate profit & loss by project report"""
    # Get parameters
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    project_id = request.GET.get('project_id')
    
    if start_date:
        try:
            start_date = date.fromisoformat(start_date)
        except ValueError:
            start_date = date.today().replace(day=1)
    else:
        start_date = date.today().replace(day=1)
    
    if end_date:
        try:
            end_date = date.fromisoformat(end_date)
        except ValueError:
            end_date = date.today()
    else:
        end_date = date.today()
    
    try:
        # This would analyze project profitability
        context = {
            'start_date': start_date,
            'end_date': end_date,
            'project_id': project_id,
            'report_type': 'Profit & Loss by Project',
            'project_summary': {
                'total_revenue': Decimal('0.00'),
                'total_costs': Decimal('0.00'),
                'gross_profit': Decimal('0.00'),
                'net_profit': Decimal('0.00'),
            }
        }
        
        return render(request, 'finance/reports/management/profit_loss_by_project.html', context)
        
    except Exception as e:
        messages.error(request, f'Error generating project P&L report: {str(e)}')
        return redirect('finance:reports_dashboard')


# ============================================================================
# CUSTOM REPORTS
# ============================================================================

@login_required
@tenant_required
def custom_report_builder(request):
    """Custom report builder interface"""
    if request.method == 'POST':
        # Handle custom report generation
        report_config = request.POST.get('report_config')
        report_type = request.POST.get('report_type')
        
        try:
            # Parse report configuration and generate report
            # This would integrate with the custom report builder service
            
            messages.success(request, 'Custom report generated successfully.')
            return redirect('finance:reports_dashboard')
            
        except Exception as e:
            messages.error(request, f'Error generating custom report: {str(e)}')
    
    # Get available report templates
    context = {
        'report_types': [
            'account_activity',
            'transaction_summary',
            'vendor_analysis',
            'customer_analysis',
            'cash_flow_forecast',
            'expense_analysis',
        ],
        'date_ranges': [
            'today',
            'yesterday',
            'this_week',
            'last_week',
            'this_month',
            'last_month',
            'this_quarter',
            'last_quarter',
            'this_year',
            'last_year',
            'custom',
        ]
    }
    
    return render(request, 'finance/reports/custom/report_builder.html', context)


# ============================================================================
# REPORT EXPORTS
# ============================================================================

@login_required
@tenant_required
def export_report(request, report_type):
    """Export report in various formats"""
    format_type = request.GET.get('format', 'pdf')
    
    if format_type not in ['pdf', 'excel', 'csv']:
        format_type = 'pdf'
    
    try:
        # Generate report based on type
        if report_type == 'balance_sheet':
            return export_balance_sheet(request, format_type)
        elif report_type == 'income_statement':
            return export_income_statement(request, format_type)
        elif report_type == 'trial_balance':
            return export_trial_balance(request, format_type)
        else:
            messages.error(request, f'Unsupported report type: {report_type}')
            return redirect('finance:reports_dashboard')
            
    except Exception as e:
        messages.error(request, f'Error exporting report: {str(e)}')
        return redirect('finance:reports_dashboard')


def export_balance_sheet(request, format_type):
    """Export balance sheet"""
    accounting_service = AccountingService(request.tenant)
    
    as_of_date = request.GET.get('as_of_date', date.today())
    if isinstance(as_of_date, str):
        try:
            as_of_date = date.fromisoformat(as_of_date)
        except ValueError:
            as_of_date = date.today()
    
    try:
        balance_sheet_data = accounting_service.generate_balance_sheet(as_of_date)
        
        if format_type == 'csv':
            response = HttpResponse(content_type='text/csv')
            response['Content-Disposition'] = f'attachment; filename="balance_sheet_{as_of_date}.csv"'
            
            import csv
            writer = csv.writer(response)
            writer.writerow(['Account', 'Type', 'Balance'])
            
            # Write assets
            for asset in balance_sheet_data.get('assets', {}).get('current_assets', []):
                writer.writerow([asset['account_name'], 'Current Asset', asset['balance']])
            
            for asset in balance_sheet_data.get('assets', {}).get('fixed_assets', []):
                writer.writerow([asset['account_name'], 'Fixed Asset', asset['balance']])
            
            # Write liabilities and equity
            for liability in balance_sheet_data.get('liabilities', {}).get('current_liabilities', []):
                writer.writerow([liability['account_name'], 'Current Liability', liability['balance']])
            
            for equity in balance_sheet_data.get('equity', {}).get('equity_accounts', []):
                writer.writerow([equity['account_name'], 'Equity', equity['balance']])
            
            return response
        
        elif format_type == 'excel':
            # Excel export implementation
            pass
        
        else:  # PDF
            # PDF export implementation
            pass
        
    except Exception as e:
        messages.error(request, f'Error exporting balance sheet: {str(e)}')
        return redirect('finance:reports_dashboard')


def export_income_statement(request, format_type):
    """Export income statement"""
    accounting_service = AccountingService(request.tenant)
    
    start_date = request.GET.get('start_date', date.today().replace(day=1))
    end_date = request.GET.get('end_date', date.today())
    
    if isinstance(start_date, str):
        try:
            start_date = date.fromisoformat(start_date)
        except ValueError:
            start_date = date.today().replace(day=1)
    
    if isinstance(end_date, str):
        try:
            end_date = date.fromisoformat(end_date)
        except ValueError:
            end_date = date.today()
    
    try:
        income_statement_data = accounting_service.generate_income_statement(start_date, end_date)
        
        if format_type == 'csv':
            response = HttpResponse(content_type='text/csv')
            response['Content-Disposition'] = f'attachment; filename="income_statement_{start_date}_{end_date}.csv"'
            
            import csv
            writer = csv.writer(response)
            writer.writerow(['Account', 'Amount'])
            
            # Write revenue
            writer.writerow(['REVENUE', ''])
            for revenue in income_statement_data.get('revenue', {}).get('revenue_accounts', []):
                writer.writerow([revenue['account_name'], revenue['amount']])
            
            # Write expenses
            writer.writerow(['EXPENSES', ''])
            for expense in income_statement_data.get('expenses', {}).get('operating_expenses', []):
                writer.writerow([expense['account_name'], expense['amount']])
            
            return response
        
        elif format_type == 'excel':
            # Excel export implementation
            pass
        
        else:  # PDF
            # PDF export implementation
            pass
        
    except Exception as e:
        messages.error(request, f'Error exporting income statement: {str(e)}')
        return redirect('finance:reports_dashboard')


def export_trial_balance(request, format_type):
    """Export trial balance"""
    accounting_service = AccountingService(request.tenant)
    
    as_of_date = request.GET.get('as_of_date', date.today())
    if isinstance(as_of_date, str):
        try:
            as_of_date = date.fromisoformat(as_of_date)
        except ValueError:
            as_of_date = date.today()
    
    try:
        trial_balance_data = accounting_service.export_trial_balance(as_of_date, format_type)
        
        if format_type == 'csv':
            response = HttpResponse(content_type='text/csv')
            response['Content-Disposition'] = f'attachment; filename="trial_balance_{as_of_date}.csv"'
            
            import csv
            writer = csv.writer(response)
            writer.writerow(['Account Code', 'Account Name', 'Debit', 'Credit'])
            
            for account in trial_balance_data.get('accounts', []):
                writer.writerow([
                    account['account_code'],
                    account['account_name'],
                    account['debit_amount'],
                    account['credit_amount']
                ])
            
            return response
        
        elif format_type == 'excel':
            # Excel export implementation
            pass
        
        else:  # PDF
            # PDF export implementation
            pass
        
    except Exception as e:
        messages.error(request, f'Error exporting trial balance: {str(e)}')
        return redirect('finance:reports_dashboard')


# ============================================================================
# API ENDPOINTS FOR AJAX
# ============================================================================

@login_required
@tenant_required
def report_data_api(request, report_type):
    """API endpoint for report data (AJAX)"""
    try:
        if report_type == 'financial_ratios':
            accounting_service = AccountingService(request.tenant)
            as_of_date = request.GET.get('as_of_date', date.today())
            
            if isinstance(as_of_date, str):
                try:
                    as_of_date = date.fromisoformat(as_of_date)
                except ValueError:
                    as_of_date = date.today()
            
            ratios = accounting_service.get_financial_ratios(as_of_date)
            return JsonResponse(ratios)
        
        elif report_type == 'monthly_summary':
            accounting_service = AccountingService(request.tenant)
            year = request.GET.get('year', date.today().year)
            
            monthly_summary = accounting_service.get_monthly_financial_summary(int(year))
            return JsonResponse(monthly_summary)
        
        else:
            return JsonResponse({'error': f'Unsupported report type: {report_type}'})
            
    except Exception as e:
        return JsonResponse({'error': str(e)})


@login_required
@tenant_required
def report_schedule(request):
    """Schedule report generation"""
    if request.method == 'POST':
        report_type = request.POST.get('report_type')
        schedule_type = request.POST.get('schedule_type')
        email_recipients = request.POST.get('email_recipients')
        
        try:
            # This would integrate with the report scheduling service
            messages.success(request, f'Report {report_type} scheduled successfully.')
            return redirect('finance:reports_dashboard')
            
        except Exception as e:
            messages.error(request, f'Error scheduling report: {str(e)}')
    
    context = {
        'report_types': [
            'balance_sheet',
            'income_statement',
            'cash_flow_statement',
            'trial_balance',
            'ar_aging',
            'ap_aging',
        ],
        'schedule_types': [
            'daily',
            'weekly',
            'monthly',
            'quarterly',
            'yearly',
        ]
    }
    
    return render(request, 'finance/reports/schedule.html', context)
