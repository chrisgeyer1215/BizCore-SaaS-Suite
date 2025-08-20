# backend/apps/finance/serializers/reports.py

from rest_framework import serializers
from decimal import Decimal

class AccountBalanceReportSerializer(serializers.Serializer):
    """Serializer for account balance reports"""
    
    account_code = serializers.CharField()
    account_name = serializers.CharField()
    account_type = serializers.CharField()
    balance = serializers.DecimalField(max_digits=15, decimal_places=2)
    formatted_balance = serializers.CharField()


class BalanceSheetSerializer(serializers.Serializer):
    """Serializer for Balance Sheet"""
    
    # Assets
    current_assets = serializers.ListField(child=AccountBalanceReportSerializer())
    fixed_assets = serializers.ListField(child=AccountBalanceReportSerializer())
    other_assets = serializers.ListField(child=AccountBalanceReportSerializer())
    total_assets = serializers.DecimalField(max_digits=15, decimal_places=2)
    
    # Liabilities
    current_liabilities = serializers.ListField(child=AccountBalanceReportSerializer())
    long_term_liabilities = serializers.ListField(child=AccountBalanceReportSerializer())
    total_liabilities = serializers.DecimalField(max_digits=15, decimal_places=2)
    
    # Equity
    equity_accounts = serializers.ListField(child=AccountBalanceReportSerializer())
    total_equity = serializers.DecimalField(max_digits=15, decimal_places=2)
    
    # Report metadata
    as_of_date = serializers.DateField()
    currency = serializers.CharField()
    generated_at = serializers.DateTimeField()


class IncomeStatementSerializer(serializers.Serializer):
    """Serializer for Income Statement"""
    
    # Revenue
    revenue_accounts = serializers.ListField(child=AccountBalanceReportSerializer())
    total_revenue = serializers.DecimalField(max_digits=15, decimal_places=2)
    
    # Cost of Goods Sold
    cogs_accounts = serializers.ListField(child=AccountBalanceReportSerializer())
    total_cogs = serializers.DecimalField(max_digits=15, decimal_places=2)
    gross_profit = serializers.DecimalField(max_digits=15, decimal_places=2)
    gross_margin = serializers.DecimalField(max_digits=5, decimal_places=2)
    
    # Operating Expenses
    expense_accounts = serializers.ListField(child=AccountBalanceReportSerializer())
    total_expenses = serializers.DecimalField(max_digits=15, decimal_places=2)
    
    # Net Income
    operating_income = serializers.DecimalField(max_digits=15, decimal_places=2)
    other_income = serializers.DecimalField(max_digits=15, decimal_places=2)
    other_expenses = serializers.DecimalField(max_digits=15, decimal_places=2)
    net_income = serializers.DecimalField(max_digits=15, decimal_places=2)
    net_margin = serializers.DecimalField(max_digits=5, decimal_places=2)
    
    # Report metadata
    period_start = serializers.DateField()
    period_end = serializers.DateField()
    currency = serializers.CharField()
    generated_at = serializers.DateTimeField()


class CashFlowSerializer(serializers.Serializer):
    """Serializer for Cash Flow Statement"""
    
    # Operating Activities
    net_income = serializers.DecimalField(max_digits=15, decimal_places=2)
    depreciation = serializers.DecimalField(max_digits=15, decimal_places=2)
    ar_change = serializers.DecimalField(max_digits=15, decimal_places=2)
    ap_change = serializers.DecimalField(max_digits=15, decimal_places=2)
    inventory_change = serializers.DecimalField(max_digits=15, decimal_places=2)
    other_operating = serializers.DecimalField(max_digits=15, decimal_places=2)
    cash_from_operations = serializers.DecimalField(max_digits=15, decimal_places=2)
    
    # Investing Activities
    asset_purchases = serializers.DecimalField(max_digits=15, decimal_places=2)
    asset_sales = serializers.DecimalField(max_digits=15, decimal_places=2)
    investments = serializers.DecimalField(max_digits=15, decimal_places=2)
    cash_from_investing = serializers.DecimalField(max_digits=15, decimal_places=2)
    
    # Financing Activities
    debt_proceeds = serializers.DecimalField(max_digits=15, decimal_places=2)
    debt_payments = serializers.DecimalField(max_digits=15, decimal_places=2)
    equity_proceeds = serializers.DecimalField(max_digits=15, decimal_places=2)
    dividends_paid = serializers.DecimalField(max_digits=15, decimal_places=2)
    cash_from_financing = serializers.DecimalField(max_digits=15, decimal_places=2)
    
    # Net Change
    net_cash_change = serializers.DecimalField(max_digits=15, decimal_places=2)
    beginning_cash = serializers.DecimalField(max_digits=15, decimal_places=2)
    ending_cash = serializers.DecimalField(max_digits=15, decimal_places=2)
    
    # Report metadata
    period_start = serializers.DateField()
    period_end = serializers.DateField()
    currency = serializers.CharField()
    generated_at = serializers.DateTimeField()


class AgingItemSerializer(serializers.Serializer):
    """Serializer for aging report items"""
    
    party_name = serializers.CharField()
    document_number = serializers.CharField()
    document_date = serializers.DateField()
    due_date = serializers.DateField()
    days_outstanding = serializers.IntegerField()
    total_amount = serializers.DecimalField(max_digits=15, decimal_places=2)
    current = serializers.DecimalField(max_digits=15, decimal_places=2)
    days_30 = serializers.DecimalField(max_digits=15, decimal_places=2)
    days_60 = serializers.DecimalField(max_digits=15, decimal_places=2)
    days_90 = serializers.DecimalField(max_digits=15, decimal_places=2)
    over_90 = serializers.DecimalField(max_digits=15, decimal_places=2)


class ARAgingSerializer(serializers.Serializer):
    """Serializer for Accounts Receivable Aging"""
    
    aging_items = serializers.ListField(child=AgingItemSerializer())
    
    # Totals
    total_outstanding = serializers.DecimalField(max_digits=15, decimal_places=2)
    total_current = serializers.DecimalField(max_digits=15, decimal_places=2)
    total_30_days = serializers.DecimalField(max_digits=15, decimal_places=2)
    total_60_days = serializers.DecimalField(max_digits=15, decimal_places=2)
    total_90_days = serializers.DecimalField(max_digits=15, decimal_places=2)
    total_over_90 = serializers.DecimalField(max_digits=15, decimal_places=2)
    
    # Percentages
    current_percentage = serializers.DecimalField(max_digits=5, decimal_places=2)
    past_due_percentage = serializers.DecimalField(max_digits=5, decimal_places=2)
    
    # Report metadata
    as_of_date = serializers.DateField()
    currency = serializers.CharField()
    generated_at = serializers.DateTimeField()


class APAgingSerializer(serializers.Serializer):
    """Serializer for Accounts Payable Aging"""
    
    aging_items = serializers.ListField(child=AgingItemSerializer())
    
    # Totals
    total_outstanding = serializers.DecimalField(max_digits=15, decimal_places=2)
    total_current = serializers.DecimalField(max_digits=15, decimal_places=2)
    total_30_days = serializers.DecimalField(max_digits=15, decimal_places=2)
    total_60_days = serializers.DecimalField(max_digits=15, decimal_places=2)
    total_90_days = serializers.DecimalField(max_digits=15, decimal_places=2)
    total_over_90 = serializers.DecimalField(max_digits=15, decimal_places=2)
    
    # Report metadata
    as_of_date = serializers.DateField()
    currency = serializers.CharField()
    generated_at = serializers.DateTimeField()


class TrialBalanceSerializer(serializers.Serializer):
    """Serializer for Trial Balance"""
    
    accounts = serializers.ListField(child=AccountBalanceReportSerializer())
    total_debits = serializers.DecimalField(max_digits=15, decimal_places=2)
    total_credits = serializers.DecimalField(max_digits=15, decimal_places=2)
    is_balanced = serializers.BooleanField()
    variance = serializers.DecimalField(max_digits=15, decimal_places=2)
    
    # Report metadata
    as_of_date = serializers.DateField()
    currency = serializers.CharField()
    generated_at = serializers.DateTimeField()