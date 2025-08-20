# backend/apps/finance/serializers/accounts.py

"""
Chart of Accounts Serializers
"""

from rest_framework import serializers
from ..models import AccountCategory, Account


class AccountCategorySerializer(serializers.ModelSerializer):
    """Account category serializer"""
    
    class Meta:
        model = AccountCategory
        fields = [
            'id', 'name', 'description', 'account_type',
            'sort_order', 'is_active', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class AccountSerializer(serializers.ModelSerializer):
    """Account serializer"""
    
    category_name = serializers.CharField(source='category.name', read_only=True)
    parent_account_name = serializers.CharField(source='parent_account.name', read_only=True)
    currency_code = serializers.CharField(source='currency.code', read_only=True)
    balance_sheet_section = serializers.ReadOnlyField()
    is_balance_sheet_account = serializers.ReadOnlyField()
    
    class Meta:
        model = Account
        fields = [
            'id', 'code', 'name', 'description', 'account_type',
            'category', 'category_name', 'parent_account', 'parent_account_name',
            'level', 'normal_balance', 'opening_balance', 'current_balance',
            'opening_balance_date', 'currency', 'currency_code',
            'is_active', 'is_system_account', 'is_bank_account',
            'is_cash_account', 'allow_manual_entries', 'require_reconciliation',
            'bank_name', 'bank_account_number', 'bank_routing_number',
            'bank_swift_code', 'default_tax_code', 'is_taxable',
            'tax_line', 'track_inventory', 'inventory_valuation_method',
            'budget_amount', 'balance_sheet_section', 'is_balance_sheet_account',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'category_name', 'parent_account_name', 'currency_code',
            'level', 'current_balance', 'balance_sheet_section',
            'is_balance_sheet_account', 'created_at', 'updated_at'
        ]

    def validate_code(self, value):
        # Check for unique code within tenant
        tenant = self.context['request'].tenant
        if Account.objects.filter(tenant=tenant, code=value).exclude(pk=self.instance.pk if self.instance else None).exists():
            raise serializers.ValidationError("Account code must be unique")
        return value

    def validate(self, data):
        # Validate parent account relationship
        if 'parent_account' in data and data['parent_account']:
            if data['parent_account'].account_type != data.get('account_type', self.instance.account_type if self.instance else None):
                raise serializers.ValidationError("Parent account must be of the same type")
        return data


class AccountTreeSerializer(serializers.ModelSerializer):
    """Account tree serializer with nested sub-accounts"""
    
    sub_accounts = serializers.SerializerMethodField()
    balance = serializers.SerializerMethodField()
    
    class Meta:
        model = Account
        fields = [
            'id', 'code', 'name', 'account_type', 'level',
            'current_balance', 'balance', 'is_active', 'sub_accounts'
        ]

    def get_sub_accounts(self, obj):
        if obj.sub_accounts.exists():
            return AccountTreeSerializer(obj.sub_accounts.filter(is_active=True), many=True, context=self.context).data
        return []

    def get_balance(self, obj):
        # Get balance with proper formatting
        return float(obj.current_balance)