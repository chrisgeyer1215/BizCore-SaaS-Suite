# backend/apps/finance/services/reporting.py

"""
Financial Reporting Service - Generate Financial Reports
"""

from django.db.models import Sum, Q, F
from decimal import Decimal
from datetime import date, datetime
from typing import Dict, List, Optional
import json

from ..models import Account, JournalEntryLine, Invoice, Bill, Payment, FiscalYear
from .accounting import AccountingService


class FinancialReportingService(AccountingService):
    """Financial reporting and analysis service"""

    def generate_balance_sheet(self, as_of_date: date = None) -> Dict:
        """Generate balance sheet report"""
        if not as_of_date:
            as_of_date = date.today()
        
        # Get all balance sheet accounts
        accounts = Account.objects.filter(
            tenant=self.tenant,
            is_active=True
        ).order_by('account_type', 'code')
        
        balance_sheet = {
            'as_of_date': as_of_date,
            'company_name': self.settings.company_name,
            'assets': {
                'current_assets': [],
                'fixed_assets': [],
                'other_assets': [],
                'total_assets': Decimal('0.00')
            },
            'liabilities': {
                'current_liabilities': [],
                'long_term_liabilities': [],
                'total_liabilities': Decimal('0.00')
            },
            'equity': {
                'equity_accounts': [],
                'total_equity': Decimal('0.00')
            }
        }
        
        for account in accounts:
            if not account.is_balance_sheet_account():
                continue
                
            balance = self.get_account_balance(account.id, as_of_date)
            
            if balance == 0:
                continue
            
            account_data = {
                'account_code': account.code,
                'account_name': account.name,
                'balance': float(balance)
            }
            
            # Categorize by account type
            if account.account_type == 'CURRENT_ASSET':
                balance_sheet['assets']['current_assets'].append(account_data)
                balance_sheet['assets']['total_assets'] += balance
            elif account.account_type in ['FIXED_ASSET', 'ASSET']:
                balance_sheet['assets']['fixed_assets'].append(account_data)
                balance_sheet['assets']['total_assets'] += balance
            elif account.account_type == 'OTHER_ASSET':
                balance_sheet['assets']['other_assets'].append(account_data)
                balance_sheet['assets']['total_assets'] += balance
            elif account.account_type == 'CURRENT_LIABILITY':
                balance_sheet['liabilities']['current_liabilities'].append(account_data)
                balance_sheet['liabilities']['total_liabilities'] += balance
            elif account.account_type in ['LONG_TERM_LIABILITY', 'LIABILITY']:
                balance_sheet['liabilities']['long_term_liabilities'].append(account_data)
                balance_sheet['liabilities']['total_liabilities'] += balance
            elif account.account_type in ['EQUITY', 'RETAINED_EARNINGS']:
                balance_sheet['equity']['equity_accounts'].append(account_data)
                balance_sheet['equity']['total_equity'] += balance
        
        # Convert Decimal to float for JSON serialization
        balance_sheet['assets']['total_assets'] = float(balance_sheet['assets']['total_assets'])
        balance_sheet['liabilities']['total_liabilities'] = float(balance_sheet['liabilities']['total_liabilities'])
        balance_sheet['equity']['total_equity'] = float(balance_sheet['equity']['total_equity'])
        
        # Calculate total liabilities and equity
        balance_sheet['total_liabilities_and_equity'] = (
            balance_sheet['liabilities']['total_liabilities'] + 
            balance_sheet['equity']['total_equity']
        )
        
        return balance_sheet

    def generate_income_statement(self, start_date: date, end_date: date) -> Dict:
        """Generate income statement (P&L) report"""
        
        income_statement = {
            'start_date': start_date,
            'end_date': end_date,
            'company_name': self.settings.company_name,
            'revenue': {
                'operating_revenue': [],
                'other_income': [],
                'total_revenue': Decimal('0.00')
            },
            'expenses': {
                'cost_of_goods_sold': [],
                'operating_expenses': [],
                'other_expenses': [],
                'total_expenses': Decimal('0.00')
            },
            'gross_profit': Decimal('0.00'),
            'operating_income': Decimal('0.00'),
            'net_income': Decimal('0.00')
        }
        
        # Get revenue and expense accounts
        accounts = Account.objects.filter(
            tenant=self.tenant,
            account_type__in=['REVENUE', 'OTHER_INCOME', 'EXPENSE', 'COST_OF_GOODS_SOLD', 'OTHER_EXPENSE'],
            is_active=True
        ).order_by('account_type', 'code')
        
        for account in accounts:
            # Get account activity for the period
            lines = JournalEntryLine.objects.filter(
                tenant=self.tenant,
                account=account,
                journal_entry__status='POSTED',
                journal_entry__entry_date__range=[start_date, end_date]
            )
            
            if account.normal_balance == 'CREDIT':  # Revenue accounts
                activity = lines.aggregate(
                    total=Sum('base_currency_credit_amount') - Sum('base_currency_debit_amount')
                )['total'] or Decimal('0.00')
            else:  # Expense accounts
                activity = lines.aggregate(
                    total=Sum('base_currency_debit_amount') - Sum('base_currency_credit_amount')
                )['total'] or Decimal('0.00')
            
            if activity == 0:
                continue
            
            account_data = {
                'account_code': account.code,
                'account_name': account.name,
                'amount': float(activity)
            }
            
            # Categorize by account type
            if account.account_type == 'REVENUE':
                income_statement['revenue']['operating_revenue'].append(account_data)
                income_statement['revenue']['total_revenue'] += activity
            elif account.account_type == 'OTHER_INCOME':
                income_statement['revenue']['other_income'].append(account_data)
                income_statement['revenue']['total_revenue'] += activity
            elif account.account_type == 'COST_OF_GOODS_SOLD':
                income_statement['expenses']['cost_of_goods_sold'].append(account_data)
                income_statement['expenses']['total_expenses'] += activity
            elif account.account_type == 'EXPENSE':
                income_statement['expenses']['operating_expenses'].append(account_data)
                income_statement['expenses']['total_expenses'] += activity
            elif account.account_type == 'OTHER_EXPENSE':
                income_statement['expenses']['other_expenses'].append(account_data)
                income_statement['expenses']['total_expenses'] += activity
        
        # Calculate totals
        total_revenue = income_statement['revenue']['total_revenue']
        total_cogs = sum(
            Decimal(str(item['amount'])) 
            for item in income_statement['expenses']['cost_of_goods_sold']
        )
        total_operating_expenses = sum(
            Decimal(str(item['amount'])) 
            for item in income_statement['expenses']['operating_expenses']
        )
        total_other_expenses = sum(
            Decimal(str(item['amount'])) 
            for item in income_statement['expenses']['other_expenses']
        )
        
        income_statement['gross_profit'] = total_revenue - total_cogs
        income_statement['operating_income'] = income_statement['gross_profit'] - total_operating_expenses
        income_statement['net_income'] = income_statement['operating_income'] - total_other_expenses
        
        # Convert Decimal to float for JSON serialization
        income_statement['revenue']['total_revenue'] = float(income_statement['revenue']['total_revenue'])
        income_statement['expenses']['total_expenses'] = float(income_statement['expenses']['total_expenses'])
        income_statement['gross_profit'] = float(income_statement['gross_profit'])
        income_statement['operating_income'] = float(income_statement['operating_income'])
        income_statement['net_income'] = float(income_statement['net_income'])
        
        return income_statement

    def generate_cash_flow_statement(self, start_date: date, end_date: date) -> Dict:
        """Generate cash flow statement"""
        
        cash_flow = {
            'start_date': start_date,
            'end_date': end_date,
            'company_name': self.settings.company_name,
            'operating_activities': {
                'net_income': Decimal('0.00'),
                'adjustments': [],
                'working_capital_changes': [],
                'net_cash_from_operations': Decimal('0.00')
            },
            'investing_activities': {
                'activities': [],
                'net_cash_from_investing': Decimal('0.00')
            },
            'financing_activities': {
                'activities': [],
                'net_cash_from_financing': Decimal('0.00')
            },
            'net_change_in_cash': Decimal('0.00'),
            'beginning_cash': Decimal('0.00'),
            'ending_cash': Decimal('0.00')
        }
        
        # Get net income from income statement
        income_statement = self.generate_income_statement(start_date, end_date)
        cash_flow['operating_activities']['net_income'] = Decimal(str(income_statement['net_income']))
        
        # Get cash and cash equivalent accounts
        cash_accounts = Account.objects.filter(
            tenant=self.tenant,
            is_cash_account=True,
            is_active=True
        )
        
        # Calculate beginning and ending cash
        beginning_cash = sum(
            self.get_account_balance(account.id, start_date - timedelta(days=1))
            for account in cash_accounts
        )
        ending_cash = sum(
            self.get_account_balance(account.id, end_date)
            for account in cash_accounts
        )
        
        cash_flow['beginning_cash'] = beginning_cash
        cash_flow['ending_cash'] = ending_cash
        cash_flow['net_change_in_cash'] = ending_cash - beginning_cash
        
        # Operating activities adjustments (simplified)
        # In a full implementation, this would include depreciation, 
        # accounts receivable changes, accounts payable changes, etc.
        
        # For now, assume net cash from operations equals net income
        # (this is a simplification - real cash flow requires more complex calculations)
        cash_flow['operating_activities']['net_cash_from_operations'] = cash_flow['operating_activities']['net_income']
        
        # Convert Decimal to float
        for section in ['operating_activities', 'investing_activities', 'financing_activities']:
            for key, value in cash_flow[section].items():
                if isinstance(value, Decimal):
                    cash_flow[section][key] = float(value)
        
        cash_flow['net_change_in_cash'] = float(cash_flow['net_change_in_cash'])
        cash_flow['beginning_cash'] = float(cash_flow['beginning_cash'])
        cash_flow['ending_cash'] = float(cash_flow['ending_cash'])
        
        return cash_flow

    def generate_ar_aging_report(self, as_of_date: date = None) -> Dict:
        """Generate accounts receivable aging report"""
        if not as_of_date:
            as_of_date = date.today()
        
        # Get all open invoices
        invoices = Invoice.objects.filter(
            tenant=self.tenant,
            status__in=['OPEN', 'SENT', 'VIEWED', 'PARTIAL'],
            amount_due__gt=0
        ).select_related('customer')
        
        aging_report = {
            'as_of_date': as_of_date,
            'company_name': self.settings.company_name,
            'customers': [],
            'summary': {
                'current': Decimal('0.00'),
                'days_1_30': Decimal('0.00'),
                'days_31_60': Decimal('0.00'),
                'days_61_90': Decimal('0.00'),
                'over_90': Decimal('0.00'),
                'total': Decimal('0.00')
            }
        }
        
        # Group by customer
        customers = {}
        for invoice in invoices:
            customer_id = invoice.customer.id
            if customer_id not in customers:
                customers[customer_id] = {
                    'customer_name': invoice.customer.name,
                    'customer_id': customer_id,
                    'invoices': [],
                    'totals': {
                        'current': Decimal('0.00'),
                        'days_1_30': Decimal('0.00'),
                        'days_31_60': Decimal('0.00'),
                        'days_61_90': Decimal('0.00'),
                        'over_90': Decimal('0.00'),
                        'total': Decimal('0.00')
                    }
                }
            
            # Calculate days overdue
            days_overdue = (as_of_date - invoice.due_date).days
            amount_due = invoice.base_currency_amount_due
            
            # Categorize by aging bucket
            bucket = 'current'
            if days_overdue > 0:
                if days_overdue <= 30:
                    bucket = 'days_1_30'
                elif days_overdue <= 60:
                    bucket = 'days_31_60'
                elif days_overdue <= 90:
                    bucket = 'days_61_90'
                else:
                    bucket = 'over_90'
            
            invoice_data = {
                'invoice_number': invoice.invoice_number,
                'invoice_date': invoice.invoice_date,
                'due_date': invoice.due_date,
                'days_overdue': max(0, days_overdue),
                'amount_due': float(amount_due),
                'bucket': bucket
            }
            
            customers[customer_id]['invoices'].append(invoice_data)
            customers[customer_id]['totals'][bucket] += amount_due
            customers[customer_id]['totals']['total'] += amount_due
            
            # Add to summary
            aging_report['summary'][bucket] += amount_due
            aging_report['summary']['total'] += amount_due
        
        # Convert to list and sort by total amount
        aging_report['customers'] = sorted(
            [
                {
                    **customer_data,
                    'totals': {k: float(v) for k, v in customer_data['totals'].items()}
                }
                for customer_data in customers.values()
            ],
            key=lambda x: x['totals']['total'],
            reverse=True
        )
        
        # Convert summary to float
        aging_report['summary'] = {
            k: float(v) for k, v in aging_report['summary'].items()
        }
        
        return aging_report

    def generate_ap_aging_report(self, as_of_date: date = None) -> Dict:
        """Generate accounts payable aging report"""
        if not as_of_date:
            as_of_date = date.today()
        
        # Get all open bills
        bills = Bill.objects.filter(
            tenant=self.tenant,
            status__in=['OPEN', 'APPROVED', 'PARTIAL'],
            amount_due__gt=0
        ).select_related('vendor')
        
        aging_report = {
            'as_of_date': as_of_date,
            'company_name': self.settings.company_name,
            'vendors': [],
            'summary': {
                'current': Decimal('0.00'),
                'days_1_30': Decimal('0.00'),
                'days_31_60': Decimal('0.00'),
                'days_61_90': Decimal('0.00'),
                'over_90': Decimal('0.00'),
                'total': Decimal('0.00')
            }
        }
        
        # Group by vendor
        vendors = {}
        for bill in bills:
            vendor_id = bill.vendor.id
            if vendor_id not in vendors:
                vendors[vendor_id] = {
                    'vendor_name': bill.vendor.company_name,
                    'vendor_id': vendor_id,
                    'bills': [],
                    'totals': {
                        'current': Decimal('0.00'),
                        'days_1_30': Decimal('0.00'),
                        'days_31_60': Decimal('0.00'),
                        'days_61_90': Decimal('0.00'),
                        'over_90': Decimal('0.00'),
                        'total': Decimal('0.00')
                    }
                }
            
            # Calculate days overdue
            days_overdue = (as_of_date - bill.due_date).days
            amount_due = bill.base_currency_amount_due
            
            # Categorize by aging bucket
            bucket = 'current'
            if days_overdue > 0:
                if days_overdue <= 30:
                    bucket = 'days_1_30'
                elif days_overdue <= 60:
                    bucket = 'days_31_60'
                elif days_overdue <= 90:
                    bucket = 'days_61_90'
                else:
                    bucket = 'over_90'
            
            bill_data = {
                'bill_number': bill.bill_number,
                'bill_date': bill.bill_date,
                'due_date': bill.due_date,
                'days_overdue': max(0, days_overdue),
                'amount_due': float(amount_due),
                'bucket': bucket
            }
            
            vendors[vendor_id]['bills'].append(bill_data)
            vendors[vendor_id]['totals'][bucket] += amount_due
            vendors[vendor_id]['totals']['total'] += amount_due
            
            # Add to summary
            aging_report['summary'][bucket] += amount_due
            aging_report['summary']['total'] += amount_due
        
        # Convert to list and sort by total amount
        aging_report['vendors'] = sorted(
            [
                {
                    **vendor_data,
                    'totals': {k: float(v) for k, v in vendor_data['totals'].items()}
                }
                for vendor_data in vendors.values()
            ],
            key=lambda x: x['totals']['total'],
            reverse=True
        )
        
        # Convert summary to float
        aging_report['summary'] = {
            k: float(v) for k, v in aging_report['summary'].items()
        }
        
        return aging_report

    def get_fiscal_year_summary(self, year: int) -> Dict:
        """Get fiscal year financial summary"""
        
        fiscal_year = FiscalYear.objects.filter(
            tenant=self.tenant,
            year=year
        ).first()
        
        if not fiscal_year:
            raise ValueError(f'Fiscal year {year} not found')
        
        # Generate income statement for the fiscal year
        income_statement = self.generate_income_statement(
            fiscal_year.start_date,
            fiscal_year.end_date
        )
        
        # Generate balance sheet as of fiscal year end
        balance_sheet = self.generate_balance_sheet(fiscal_year.end_date)
        
        return {
            'fiscal_year': year,
            'start_date': fiscal_year.start_date,
            'end_date': fiscal_year.end_date,
            'total_revenue': Decimal(str(income_statement['revenue']['total_revenue'])),
            'total_expenses': Decimal(str(income_statement['expenses']['total_expenses'])),
            'total_cogs': sum(
                Decimal(str(item['amount'])) 
                for item in income_statement['expenses']['cost_of_goods_sold']
            ),
            'net_income': Decimal(str(income_statement['net_income'])),
            'total_assets': Decimal(str(balance_sheet['assets']['total_assets'])),
            'total_liabilities': Decimal(str(balance_sheet['liabilities']['total_liabilities'])),
            'total_equity': Decimal(str(balance_sheet['equity']['total_equity']))
        }

    def export_report_csv(self, report_data: Dict, output_path: str):
        """Export report data to CSV"""
        import csv
        
        # This is a simplified implementation
        # In practice, you'd want different CSV formats for different report types
        
        with open(output_path, 'w', newline='') as csvfile:
            writer = csv.writer(csvfile)
            
            # Write header
            writer.writerow(['Report Data'])
            writer.writerow(['Generated:', datetime.now().strftime('%Y-%m-%d %H:%M:%S')])
            writer.writerow([])
            
            # Write data (simplified - would need more complex logic for different reports)
            for key, value in report_data.items():
                if isinstance(value, (str, int, float)):
                    writer.writerow([key, value])

    def export_report_pdf(self, report_data: Dict, output_path: str):
        """Export report data to PDF"""
        # This would use reportlab or similar to create formatted PDF reports
        # For now, just a placeholder
        pass