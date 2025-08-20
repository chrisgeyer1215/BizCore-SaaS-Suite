# backend/apps/finance/serializers/currency.py

"""
Multi-Currency Support Serializers
"""

from rest_framework import serializers
from ..models import Currency, ExchangeRate


class CurrencySerializer(serializers.ModelSerializer):
    """Currency serializer"""
    
    class Meta:
        model = Currency
        fields = [
            'id', 'code', 'name', 'symbol', 'decimal_places',
            'is_active', 'is_base_currency', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def validate_code(self, value):
        if len(value) != 3:
            raise serializers.ValidationError("Currency code must be exactly 3 characters")
        return value.upper()

    def validate_decimal_places(self, value):
        if not 0 <= value <= 8:
            raise serializers.ValidationError("Decimal places must be between 0 and 8")
        return value


class ExchangeRateSerializer(serializers.ModelSerializer):
    """Exchange rate serializer"""
    
    from_currency_code = serializers.CharField(source='from_currency.code', read_only=True)
    to_currency_code = serializers.CharField(source='to_currency.code', read_only=True)
    from_currency_name = serializers.CharField(source='from_currency.name', read_only=True)
    to_currency_name = serializers.CharField(source='to_currency.name', read_only=True)
    
    class Meta:
        model = ExchangeRate
        fields = [
            'id', 'from_currency', 'from_currency_code', 'from_currency_name',
            'to_currency', 'to_currency_code', 'to_currency_name',
            'rate', 'effective_date', 'source', 'created_date'
        ]
        read_only_fields = [
            'id', 'from_currency_code', 'from_currency_name',
            'to_currency_code', 'to_currency_name', 'created_date'
        ]

    def validate_rate(self, value):
        if value <= 0:
            raise serializers.ValidationError("Exchange rate must be positive")
        return value

    def validate(self, data):
        if data['from_currency'] == data['to_currency']:
            raise serializers.ValidationError("From and to currencies cannot be the same")
        return data