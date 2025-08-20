# backend/apps/finance/serializers/dashboard.py

from rest_framework import serializers
from decimal import Decimal

class KPISerializer(serializers.Serializer):
    """Serializer for Key Performance Indicators"""
    
    label = serializers.CharField()
    value = serializers.DecimalField(max_digits=15, decimal_places=2)
    formatted_value = serializers.CharField()
    change_percentage = serializers.DecimalField(max_digits=5, decimal_places=2, required=False)
    trend = serializers.ChoiceField(choices=['up', 'down', 'neutral'], required=False)
    icon = serializers.CharField(required=False)
    color = serializers.CharField(required=False)


class ChartDataSerializer(serializers.Serializer):
    """Serializer for chart data"""
    
    labels = serializers.ListField(child=serializers.CharField())
    datasets = serializers.ListField()
    options = serializers.DictField(required=False)


class FinanceDashboardSerializer(serializers.Serializer):
    """Comprehensive serializer for Finance Dashboard"""
    
    # Key Performance Indicators
    total_revenue = KPISerializer()
    total_expenses = KPISerializer()
    net_income = KPISerializer()
    gross_margin = KPISerializer()
    
    # Cash Flow
    cash_balance = KPISerializer()
    accounts_receivable = KPISerializer()
    accounts_payable = KPISerializer()
    
    # Aging Summary
    ar_current = serializers.DecimalField(max_digits=15, decimal_places=2)
    ar_30_days = serializers.DecimalField(max_digits=15, decimal_places=2)
    ar_60_days = serializers.DecimalField(max_digits=15, decimal_places=2)
    ar_90_days = serializers.DecimalField(max_digits=15, decimal_places=2)
    ar_over_90 = serializers.DecimalField(max_digits=15, decimal_places=2)
    
    ap_current = serializers.DecimalField(max_digits=15, decimal_places=2)
    ap_30_days = serializers.DecimalField(max_digits=15, decimal_places=2)
    ap_60_days = serializers.DecimalField(max_digits=15, decimal_places=2)
    ap_90_days = serializers.DecimalField(max_digits=15, decimal_places=2)
    ap_over_90 = serializers.DecimalField(max_digits=15, decimal_places=2)
    
    # Charts
    revenue_trend = ChartDataSerializer()
    expense_breakdown = ChartDataSerializer()
    cash_flow_forecast = ChartDataSerializer()
    
    # Recent Transactions
    recent_invoices = serializers.ListField()
    recent_payments = serializers.ListField()
    recent_bills = serializers.ListField()
    
    # Alerts
    overdue_invoices_count = serializers.IntegerField()
    overdue_bills_count = serializers.IntegerField()
    low_cash_alert = serializers.BooleanField()
    
    # Period Information
    period_start = serializers.DateField()
    period_end = serializers.DateField()
    last_updated = serializers.DateTimeField()