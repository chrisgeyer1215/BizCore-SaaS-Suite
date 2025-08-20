# backend/apps/finance/serializers/invoices.py

from rest_framework import serializers
from django.db import transaction
from ..models import Invoice, InvoiceItem
from .base import BaseFinanceSerializer

class InvoiceItemSerializer(BaseFinanceSerializer):
    """Serializer for Invoice Items"""
    
    product_name = serializers.CharField(source='product.name', read_only=True)
    revenue_account_name = serializers.CharField(source='revenue_account.name', read_only=True)
    tax_code_name = serializers.CharField(source='tax_code.name', read_only=True)
    
    class Meta:
        model = InvoiceItem
        fields = [
            'id', 'line_number', 'item_type', 'product', 'product_name',
            'description', 'sku', 'quantity', 'unit_price', 'discount_rate',
            'line_total', 'revenue_account', 'revenue_account_name',
            'tax_code', 'tax_code_name', 'tax_rate', 'tax_amount',
            'is_tax_inclusive', 'project', 'department', 'location',
            'job_number', 'warehouse', 'unit_cost', 'total_cost'
        ]


class InvoiceSerializer(BaseFinanceSerializer):
    """Detailed serializer for Invoice"""
    
    customer_name = serializers.CharField(source='customer.name', read_only=True)
    currency_code = serializers.CharField(source='currency.code', read_only=True)
    invoice_items = InvoiceItemSerializer(many=True)
    days_until_due = serializers.IntegerField(read_only=True)
    days_overdue = serializers.IntegerField(read_only=True)
    is_overdue = serializers.BooleanField(read_only=True)
    
    class Meta:
        model = Invoice
        fields = [
            'id', 'invoice_number', 'invoice_type', 'reference_number',
            'purchase_order_number', 'customer', 'customer_name',
            'customer_email', 'customer_contact', 'invoice_date', 'due_date',
            'sent_date', 'viewed_date', 'service_period_start',
            'service_period_end', 'status', 'approved_by', 'approved_date',
            'currency', 'currency_code', 'exchange_rate', 'subtotal',
            'discount_amount', 'discount_percentage', 'tax_amount',
            'shipping_amount', 'total_amount', 'amount_paid', 'amount_due',
            'base_currency_total', 'base_currency_amount_paid',
            'base_currency_amount_due', 'billing_address', 'shipping_address',
            'payment_terms', 'payment_instructions', 'is_recurring',
            'recurring_interval_days', 'next_invoice_date', 'description',
            'notes', 'footer_text', 'customer_message', 'internal_notes',
            'shipping_method', 'tracking_number', 'shipped_date',
            'delivery_date', 'online_payment_enabled', 'view_count',
            'last_reminder_sent', 'reminder_count', 'days_until_due',
            'days_overdue', 'is_overdue', 'invoice_items',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'invoice_number', 'subtotal', 'tax_amount', 'total_amount',
            'amount_paid', 'amount_due', 'base_currency_total',
            'base_currency_amount_paid', 'base_currency_amount_due',
            'approved_by', 'approved_date', 'sent_date', 'viewed_date',
            'view_count', 'last_reminder_sent', 'reminder_count',
            'days_until_due', 'days_overdue', 'is_overdue',
            'created_at', 'updated_at'
        ]
    
    @transaction.atomic
    def create(self, validated_data):
        """Create invoice with items"""
        items_data = validated_data.pop('invoice_items')
        invoice = Invoice.objects.create(**validated_data)
        
        for item_data in items_data:
            InvoiceItem.objects.create(
                invoice=invoice,
                **item_data
            )
        
        invoice.calculate_totals()
        return invoice


class InvoiceListSerializer(BaseFinanceSerializer):
    """Lightweight serializer for Invoice lists"""
    
    customer_name = serializers.CharField(source='customer.name', read_only=True)
    currency_code = serializers.CharField(source='currency.code', read_only=True)
    is_overdue = serializers.BooleanField(read_only=True)
    
    class Meta:
        model = Invoice
        fields = [
            'id', 'invoice_number', 'customer_name', 'invoice_date',
            'due_date', 'status', 'total_amount', 'amount_due',
            'currency_code', 'is_overdue'
        ]


class InvoiceCreateSerializer(serializers.Serializer):
    """Serializer for creating invoices"""
    
    customer = serializers.IntegerField()
    invoice_date = serializers.DateField()
    due_date = serializers.DateField()
    currency = serializers.CharField(max_length=3)
    description = serializers.CharField(required=False)
    notes = serializers.CharField(required=False)
    items = InvoiceItemSerializer(many=True)
    
    def validate(self, data):
        """Validate invoice data"""
        if data['due_date'] < data['invoice_date']:
            raise serializers.ValidationError("Due date cannot be before invoice date")
        return data


class InvoiceSendSerializer(serializers.Serializer):
    """Serializer for sending invoices"""
    
    invoice_ids = serializers.ListField(
        child=serializers.IntegerField(),
        min_length=1
    )
    send_copy_to = serializers.EmailField(required=False)
    custom_message = serializers.CharField(required=False)