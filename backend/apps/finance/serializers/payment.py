# backend/apps/finance/serializers/payments.py

from rest_framework import serializers
from ..models import Payment, PaymentApplication
from .base import BaseFinanceSerializer

class PaymentApplicationSerializer(BaseFinanceSerializer):
    """Serializer for Payment Applications"""
    
    invoice_number = serializers.CharField(source='invoice.invoice_number', read_only=True)
    bill_number = serializers.CharField(source='bill.bill_number', read_only=True)
    
    class Meta:
        model = PaymentApplication
        fields = [
            'id', 'payment', 'invoice', 'invoice_number', 'bill',
            'bill_number', 'amount_applied', 'discount_amount',
            'application_date', 'exchange_rate',
            'base_currency_amount_applied', 'notes'
        ]
        read_only_fields = [
            'id', 'application_date', 'base_currency_amount_applied'
        ]


class PaymentSerializer(BaseFinanceSerializer):
    """Detailed serializer for Payment"""
    
    customer_name = serializers.CharField(source='customer.name', read_only=True)
    vendor_name = serializers.CharField(source='vendor.company_name', read_only=True)
    bank_account_name = serializers.CharField(source='bank_account.name', read_only=True)
    currency_code = serializers.CharField(source='currency.code', read_only=True)
    applications = PaymentApplicationSerializer(many=True, read_only=True)
    
    class Meta:
        model = Payment
        fields = [
            'id', 'payment_number', 'reference_number',
            'external_transaction_id', 'payment_type', 'payment_method',
            'payment_date', 'status', 'customer', 'customer_name',
            'vendor', 'vendor_name', 'currency', 'currency_code',
            'amount', 'exchange_rate', 'base_currency_amount',
            'bank_account', 'bank_account_name', 'check_number',
            'check_date', 'card_last_four', 'card_type',
            'processor_name', 'processor_transaction_id',
            'processing_fee', 'processing_fee_account',
            'description', 'notes', 'reconciled_date',
            'reconciled_by', 'applications', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'payment_number', 'base_currency_amount',
            'reconciled_date', 'reconciled_by', 'applications',
            'created_at', 'updated_at'
        ]


class PaymentListSerializer(BaseFinanceSerializer):
    """Lightweight serializer for Payment lists"""
    
    party_name = serializers.SerializerMethodField()
    currency_code = serializers.CharField(source='currency.code', read_only=True)
    
    class Meta:
        model = Payment
        fields = [
            'id', 'payment_number', 'payment_type', 'payment_method',
            'payment_date', 'status', 'party_name', 'amount',
            'currency_code'
        ]
    
    def get_party_name(self, obj):
        if obj.customer:
            return obj.customer.name
        elif obj.vendor:
            return obj.vendor.company_name
        return "Unknown"


class PaymentCreateSerializer(serializers.Serializer):
    """Serializer for creating payments"""
    
    payment_type = serializers.ChoiceField(choices=Payment.PAYMENT_TYPE_CHOICES)
    payment_method = serializers.ChoiceField(choices=Payment.PAYMENT_METHOD_CHOICES)
    payment_date = serializers.DateField()
    amount = serializers.DecimalField(max_digits=15, decimal_places=2)
    currency = serializers.CharField(max_length=3)
    bank_account = serializers.IntegerField()
    customer = serializers.IntegerField(required=False)
    vendor = serializers.IntegerField(required=False)
    reference_number = serializers.CharField(required=False)
    description = serializers.CharField(required=False)
    
    # Payment method specific fields
    check_number = serializers.CharField(required=False)
    check_date = serializers.DateField(required=False)
    
    def validate(self, data):
        """Validate payment data"""
        payment_type = data.get('payment_type')
        
        if payment_type == 'RECEIVED' and not data.get('customer'):
            raise serializers.ValidationError("Customer is required for received payments")
        elif payment_type == 'MADE' and not data.get('vendor'):
            raise serializers.ValidationError("Vendor is required for made payments")
        
        return data