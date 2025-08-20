# backend/apps/finance/serializers/base.py

from rest_framework import serializers
from django.contrib.auth import get_user_model
from decimal import Decimal
from apps.core.serializers import TenantAwareModelSerializer

User = get_user_model()

class BaseFinanceSerializer(TenantAwareModelSerializer):
    """Base serializer for all finance models"""
    
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True)
    updated_by_name = serializers.CharField(source='updated_by.get_full_name', read_only=True)
    
    class Meta:
        abstract = True
        
    def validate_amount(self, value):
        """Validate amount fields"""
        if value and value < 0:
            raise serializers.ValidationError("Amount cannot be negative")
        return value
    
    def validate_currency_amount(self, value):
        """Validate currency amounts with proper decimal places"""
        if value and value.as_tuple().exponent < -2:
            raise serializers.ValidationError("Amount cannot have more than 2 decimal places")
        return value


class TenantAwareSerializer(serializers.ModelSerializer):
    """Tenant-aware serializer mixin"""
    
    class Meta:
        abstract = True
        
    def create(self, validated_data):
        """Add tenant to validated data"""
        validated_data['tenant'] = self.context['request'].tenant
        return super().create(validated_data)