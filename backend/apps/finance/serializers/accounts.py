# backend/apps/finance/serializers/accounts.py

from rest_framework import serializers
from ..models import AccountCategory, Account
from .base import BaseFinanceSerializer

class AccountCategorySerializer(BaseFinanceSerializer):
    """Serializer for Account Category"""
    
    class Meta:
        model = AccountCategory
        fields = [
            'id', 'name', 'description', 'account_type', 'sort_order',
            'is_active', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class AccountSerializer(BaseFinanceSerializer):
    """Detailed serializer for Account"""
    
    category_name = serializers.CharField(source='category.name', read_only=True)
    parent_account_name = serializers.CharField(source='parent_account.name', read_only=True)
    current_balance_display = serializers.SerializerMethodField()
    balance_sheet_section = serializers.CharField(read_only=True)
    is_balance_sheet_account = serializers.BooleanField(read_only=True)
    
    class Meta:
        model = Account
        fields = [
            'id', 'code', 'name', 'description', 'account_type',
            'category', 'category_name', 'parent_account', 'parent_account_name',
            'level', 'normal_balance', 'opening_balance', 'current_balance',
            'current_balance_display', 'opening_balance_date',
            'currency', 'is_active', 'is_system_account', 'is_bank_account',
            'is_cash_account', 'allow_manual_entries', 'require_reconciliation',
            'bank_name', 'bank_account_number', 'bank_routing_number',
            'default_tax_code', 'is_taxable', 'track_inventory',
            'budget_amount', 'balance_sheet_section', 'is_balance_sheet_account',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'level', 'current_balance', 'current_balance_display',
            'balance_sheet_section', 'is_balance_sheet_account',
            'created_at', 'updated_at'
        ]
    
    def get_is_effective(self, obj):
        """Check if tax code is currently effective"""
        return obj.is_effective()
    
    def validate_rate(self, value):
        """Validate tax rate"""
        if value < 0 or value > 100:
            raise serializers.ValidationError("Tax rate must be between 0 and 100")
        return value


class TaxGroupItemSerializer(BaseFinanceSerializer):
    """Serializer for Tax Group Item"""
    
    tax_code_name = serializers.CharField(source='tax_code.name', read_only=True)
    tax_code_rate = serializers.DecimalField(
        source='tax_code.rate', max_digits=8, decimal_places=4, read_only=True
    )
    
    class Meta:
        model = TaxGroupItem
        fields = [
            'id', 'tax_group', 'tax_code', 'tax_code_name', 'tax_code_rate',
            'sequence', 'apply_to', 'is_active', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class TaxGroupSerializer(BaseFinanceSerializer):
    """Serializer for Tax Group"""
    
    tax_group_items = TaxGroupItemSerializer(many=True, read_only=True)
    total_rate = serializers.SerializerMethodField()
    
    class Meta:
        model = TaxGroup
        fields = [
            'id', 'name', 'description', 'is_active', 'total_rate',
            'tax_group_items', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'total_rate', 'created_at', 'updated_at']
    
    def get_total_rate(self, obj):
        """Calculate total tax rate for the group"""
        return sum(
            item.tax_code.rate for item in obj.tax_group_items.filter(is_active=True)
        )_current_balance_display(self, obj):
        """Format current balance for display"""
        if obj.normal_balance == 'DEBIT':
            return f"${obj.current_balance:,.2f} DR" if obj.current_balance >= 0 else f"${abs(obj.current_balance):,.2f} CR"
        else:
            return f"${obj.current_balance:,.2f} CR" if obj.current_balance >= 0 else f"${abs(obj.current_balance):,.2f} DR"
    
    def validate_code(self, value):
        """Validate account code uniqueness"""
        if self.instance:
            if Account.objects.filter(
                tenant=self.context['request'].tenant,
                code=value
            ).exclude(pk=self.instance.pk).exists():
                raise serializers.ValidationError("Account code must be unique")
        else:
            if Account.objects.filter(
                tenant=self.context['request'].tenant,
                code=value
            ).exists():
                raise serializers.ValidationError("Account code must be unique")
        return value


class AccountListSerializer(BaseFinanceSerializer):
    """Lightweight serializer for Account lists"""
    
    category_name = serializers.CharField(source='category.name', read_only=True)
    current_balance_display = serializers.SerializerMethodField()
    
    class Meta:
        model = Account
        fields = [
            'id', 'code', 'name', 'account_type', 'category_name',
            'current_balance', 'current_balance_display', 'is_active'
        ]
    
    def get_current_balance_display(self, obj):
        """Format current balance for display"""
        return f"${obj.current_balance:,.2f}"


class AccountBalanceSerializer(serializers.Serializer):
    """Serializer for account balance queries"""
    
    account_id = serializers.IntegerField()
    as_of_date = serializers.DateField(required=False)
    currency = serializers.CharField(max_length=3, required=False)
    balance = serializers.DecimalField(max_digits=15, decimal_places=2, read_only=True)
    base_currency_balance = serializers.DecimalField(max_digits=15, decimal_places=2, read_only=True)