# backend/apps/finance/serializers/tax.py

"""
Tax Management Serializers
"""

from rest_framework import serializers
from ..models import TaxCode, TaxGroup, TaxGroupItem


class TaxCodeSerializer(serializers.ModelSerializer):
    """Tax code serializer"""
    
    tax_collected_account_name = serializers.CharField(source='tax_collected_account.name', read_only=True)
    tax_paid_account_name = serializers.CharField(source='tax_paid_account.name', read_only=True)
    is_effective = serializers.SerializerMethodField()
    
    class Meta:
        model = TaxCode
        fields = [
            'id', 'code', 'name', 'description', 'tax_type',
            'calculation_method', 'rate', 'fixed_amount',
            'country', 'state_province', 'city',
            'tax_collected_account', 'tax_collected_account_name',
            'tax_paid_account', 'tax_paid_account_name',
            'is_active', 'is_compound', 'is_recoverable',
            'apply_to_shipping', 'effective_from', 'effective_to',
            'tax_authority', 'reporting_code', 'is_effective',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'tax_collected_account_name', 'tax_paid_account_name',
            'is_effective', 'created_at', 'updated_at'
        ]

    def get_is_effective(self, obj):
        return obj.is_effective()

    def validate_rate(self, value):
        if value < 0 or value > 100:
            raise serializers.ValidationError("Tax rate must be between 0 and 100")
        return value

    def validate(self, data):
        if data['calculation_method'] == 'FIXED' and not data.get('fixed_amount'):
            raise serializers.ValidationError("Fixed amount is required for fixed calculation method")
        if data['calculation_method'] == 'PERCENTAGE' and not data.get('rate'):
            raise serializers.ValidationError("Rate is required for percentage calculation method")
        return data


class TaxGroupItemSerializer(serializers.ModelSerializer):
    """Tax group item serializer"""
    
    tax_code_name = serializers.CharField(source='tax_code.name', read_only=True)
    tax_code_rate = serializers.DecimalField(source='tax_code.rate', max_digits=8, decimal_places=4, read_only=True)
    
    class Meta:
        model = TaxGroupItem
        fields = [
            'id', 'tax_code', 'tax_code_name', 'tax_code_rate',
            'sequence', 'apply_to', 'is_active'
        ]
        read_only_fields = ['id', 'tax_code_name', 'tax_code_rate']


class TaxGroupSerializer(serializers.ModelSerializer):
    """Tax group serializer"""
    
    tax_group_items = TaxGroupItemSerializer(many=True, read_only=True)
    total_rate = serializers.SerializerMethodField()
    
    class Meta:
        model = TaxGroup
        fields = [
            'id', 'name', 'description', 'is_active',
            'tax_group_items', 'total_rate', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'total_rate', 'created_at', 'updated_at']

    def get_total_rate(self, obj):
        total = 0
        for item in obj.tax_group_items.filter(is_active=True):
            total += item.tax_code.rate
        return total