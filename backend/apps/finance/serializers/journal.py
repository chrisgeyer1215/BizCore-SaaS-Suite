# backend/apps/finance/serializers/journal.py

"""
Journal Entry Serializers
"""

from rest_framework import serializers
from decimal import Decimal
from ..models import JournalEntry, JournalEntryLine


class JournalEntryLineSerializer(serializers.ModelSerializer):
    """Journal entry line serializer"""
    
    account_name = serializers.CharField(source='account.name', read_only=True)
    account_code = serializers.CharField(source='account.code', read_only=True)
    customer_name = serializers.CharField(source='customer.name', read_only=True)
    vendor_name = serializers.CharField(source='vendor.company_name', read_only=True)
    product_name = serializers.CharField(source='product.name', read_only=True)
    amount = serializers.ReadOnlyField()
    is_debit = serializers.ReadOnlyField()
    
    class Meta:
        model = JournalEntryLine
        fields = [
            'id', 'line_number', 'account', 'account_name', 'account_code',
            'description', 'debit_amount', 'credit_amount',
            'base_currency_debit_amount', 'base_currency_credit_amount',
            'customer', 'customer_name', 'vendor', 'vendor_name',
            'product', 'product_name', 'project', 'department', 'location',
            'tax_code', 'tax_amount', 'quantity', 'unit_cost',
            'amount', 'is_debit'
        ]
        read_only_fields = ['id', 'account_name', 'account_code', 'customer_name', 'vendor_name', 'product_name', 'amount', 'is_debit']

    def validate(self, data):
        if data.get('debit_amount') and data.get('credit_amount'):
            raise serializers.ValidationError("Line cannot have both debit and credit amounts")
        if not data.get('debit_amount') and not data.get('credit_amount'):
            raise serializers.ValidationError("Line must have either debit or credit amount")
        return data


class JournalEntrySerializer(serializers.ModelSerializer):
    """Journal entry serializer"""
    
    journal_lines = JournalEntryLineSerializer(many=True, read_only=True)
    currency_code = serializers.CharField(source='currency.code', read_only=True)
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True)
    posted_by_name = serializers.CharField(source='posted_by.get_full_name', read_only=True)
    is_balanced = serializers.SerializerMethodField()
    
    class Meta:
        model = JournalEntry
        fields = [
            'id', 'entry_number', 'reference_number', 'entry_date',
            'status', 'entry_type', 'description', 'notes',
            'source_document_type', 'source_document_id', 'source_document_number',
            'total_debit', 'total_credit', 'currency', 'currency_code',
            'exchange_rate', 'base_currency_total_debit', 'base_currency_total_credit',
            'created_by', 'created_by_name', 'posted_by', 'posted_by_name',
            'posted_date', 'approved_by', 'approved_date', 'reversed_entry',
            'reversal_reason', 'financial_period', 'attachments',
            'journal_lines', 'is_balanced', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'entry_number', 'currency_code', 'created_by_name',
            'posted_by_name', 'total_debit', 'total_credit',
            'base_currency_total_debit', 'base_currency_total_credit',
            'posted_date', 'approved_date', 'is_balanced', 'created_at', 'updated_at'
        ]

    def get_is_balanced(self, obj):
        return abs(obj.total_debit - obj.total_credit) < Decimal('0.01')


class JournalEntryCreateSerializer(serializers.ModelSerializer):
    """Journal entry creation serializer with lines"""
    
    lines = JournalEntryLineSerializer(many=True, write_only=True)
    
    class Meta:
        model = JournalEntry
        fields = [
            'entry_date', 'entry_type', 'description', 'notes',
            'reference_number', 'currency', 'exchange_rate', 'lines'
        ]

    def validate_lines(self, lines):
        if len(lines) < 2:
            raise serializers.ValidationError("Journal entry must have at least 2 lines")
        
        total_debit = sum(line.get('debit_amount', 0) for line in lines)
        total_credit = sum(line.get('credit_amount', 0) for line in lines)
        
        if abs(total_debit - total_credit) > Decimal('0.01'):
            raise serializers.ValidationError("Journal entry must be balanced (debits = credits)")
        
        return lines

    def create(self, validated_data):
        lines_data = validated_data.pop('lines')
        journal_entry = JournalEntry.objects.create(**validated_data)
        
        for i, line_data in enumerate(lines_data, 1):
            line_data['line_number'] = i
            JournalEntryLine.objects.create(journal_entry=journal_entry, **line_data)
        
        journal_entry.calculate_totals()
        return journal_entry