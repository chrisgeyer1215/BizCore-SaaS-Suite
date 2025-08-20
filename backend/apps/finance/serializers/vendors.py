# backend/apps/finance/serializers/vendors.py

from rest_framework import serializers
from django.db import transaction
from ..models import Vendor, VendorContact, Bill, BillItem
from .base import BaseFinanceSerializer

class VendorContactSerializer(BaseFinanceSerializer):
    """Serializer for Vendor Contacts"""
    
    full_name = serializers.SerializerMethodField()
    
    class Meta:
        model = VendorContact
        fields = [
            'id', 'contact_type', 'first_name', 'last_name', 'full_name',
            'title', 'email', 'phone', 'mobile', 'is_primary',
            'receive_communications'
        ]
    
    def get_full_name(self, obj):
        return f"{obj.first_name} {obj.last_name}"


class VendorSerializer(BaseFinanceSerializer):
    """Detailed serializer for Vendor"""
    
    currency_code = serializers.CharField(source='currency.code', read_only=True)
    default_expense_account_name = serializers.CharField(
        source='default_expense_account.name', read_only=True
    )
    outstanding_balance = serializers.SerializerMethodField()
    ytd_purchases = serializers.SerializerMethodField()
    contacts = VendorContactSerializer(many=True, read_only=True)
    
    class Meta:
        model = Vendor
        fields = [
            'id', 'vendor_number', 'company_name', 'display_name',
            'vendor_type', 'status', 'primary_contact', 'email',
            'phone', 'mobile', 'fax', 'website', 'billing_address',
            'shipping_address', 'remit_to_address', 'payment_terms',
            'payment_terms_days', 'credit_limit', 'current_balance',
            'currency', 'currency_code', 'tax_id', 'vat_number',
            'is_tax_exempt', 'tax_exempt_number', 'is_1099_vendor',
            'default_expense_account', 'default_expense_account_name',
            'accounts_payable_account', 'bank_name', 'bank_account_number',
            'routing_number', 'swift_code', 'iban', 'is_inventory_supplier',
            'supplier_code', 'average_payment_days', 'on_time_delivery_rate',
            'quality_rating', 'notes', 'internal_notes', 'approved_by',
            'approved_date', 'outstanding_balance', 'ytd_purchases',
            'contacts', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'vendor_number', 'current_balance', 'average_payment_days',
            'on_time_delivery_rate', 'quality_rating', 'approved_by',
            'approved_date', 'outstanding_balance', 'ytd_purchases',
            'created_at', 'updated_at'
        ]
    
    def get_outstanding_balance(self, obj):
        """Get vendor outstanding balance"""
        return obj.get_outstanding_balance()
    
    def get_ytd_purchases(self, obj):
        """Get year-to-date purchases"""
        return obj.get_ytd_purchases()


class VendorListSerializer(BaseFinanceSerializer):
    """Lightweight serializer for Vendor lists"""
    
    currency_code = serializers.CharField(source='currency.code', read_only=True)
    outstanding_balance = serializers.SerializerMethodField()
    
    class Meta:
        model = Vendor
        fields = [
            'id', 'vendor_number', 'company_name', 'vendor_type',
            'status', 'email', 'phone', 'current_balance',
            'outstanding_balance', 'currency_code'
        ]
    
    def get_outstanding_balance(self, obj):
        return obj.get_outstanding_balance()


class BillItemSerializer(BaseFinanceSerializer):
    """Serializer for Bill Items"""
    
    product_name = serializers.CharField(source='product.name', read_only=True)
    expense_account_name = serializers.CharField(source='expense_account.name', read_only=True)
    
    class Meta:
        model = BillItem
        fields = [
            'id', 'line_number', 'item_type', 'product', 'product_name',
            'description', 'sku', 'quantity', 'unit_cost', 'discount_rate',
            'line_total', 'expense_account', 'expense_account_name',
            'tax_code', 'tax_rate', 'tax_amount', 'project', 'department',
            'location', 'job_number', 'warehouse', 'lot_number',
            'serial_numbers'
        ]


class BillSerializer(BaseFinanceSerializer):
    """Detailed serializer for Bill"""
    
    vendor_name = serializers.CharField(source='vendor.company_name', read_only=True)
    currency_code = serializers.CharField(source='currency.code', read_only=True)
    bill_items = BillItemSerializer(many=True)
    days_until_due = serializers.IntegerField(read_only=True)
    days_overdue = serializers.IntegerField(read_only=True)
    is_overdue = serializers.BooleanField(read_only=True)
    can_be_approved = serializers.BooleanField(read_only=True)
    
    class Meta:
        model = Bill
        fields = [
            'id', 'bill_number', 'vendor_invoice_number', 'reference_number',
            'bill_type', 'vendor', 'vendor_name', 'bill_date', 'due_date',
            'received_date', 'service_period_start', 'service_period_end',
            'status', 'approved_by', 'approved_date', 'currency',
            'currency_code', 'exchange_rate', 'subtotal', 'discount_amount',
            'tax_amount', 'total_amount', 'amount_paid', 'amount_due',
            'base_currency_subtotal', 'base_currency_total',
            'base_currency_amount_paid', 'base_currency_amount_due',
            'billing_address', 'source_purchase_order', 'is_recurring',
            'recurring_interval_days', 'next_bill_date', 'parent_bill',
            'description', 'notes', 'terms', 'private_notes',
            'workflow_state', 'days_until_due', 'days_overdue',
            'is_overdue', 'can_be_approved', 'bill_items',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'bill_number', 'subtotal', 'tax_amount', 'total_amount',
            'amount_paid', 'amount_due', 'base_currency_subtotal',
            'base_currency_total', 'base_currency_amount_paid',
            'base_currency_amount_due', 'approved_by', 'approved_date',
            'days_until_due', 'days_overdue', 'is_overdue',
            'can_be_approved', 'created_at', 'updated_at'
        ]
    
    @transaction.atomic
    def create(self, validated_data):
        """Create bill with items"""
        items_data = validated_data.pop('bill_items')
        bill = Bill.objects.create(**validated_data)
        
        for item_data in items_data:
            BillItem.objects.create(
                bill=bill,
                **item_data
            )
        
        bill.calculate_totals()
        return bill


class BillListSerializer(BaseFinanceSerializer):
    """Lightweight serializer for Bill lists"""
    
    vendor_name = serializers.CharField(source='vendor.company_name', read_only=True)
    currency_code = serializers.CharField(source='currency.code', read_only=True)
    is_overdue = serializers.BooleanField(read_only=True)
    
    class Meta:
        model = Bill
        fields = [
            'id', 'bill_number', 'vendor_name', 'bill_date', 'due_date',
            'status', 'total_amount', 'amount_due', 'currency_code',
            'is_overdue'
        ]