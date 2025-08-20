# backend/apps/finance/serializers/journal.py

from rest_framework import serializers
from django.db import transaction
from ..models import JournalEntry, JournalEntryLine, Account
from .base import BaseFinanceSerializer

class JournalEntryLineSerializer(BaseFinanceSerializer):
    """Serializer for Journal Entry Lines"""
    
    account_code = serializers.CharField(source='account.code', read_only=True)
    account_name = serializers.CharField(source='account.name', read_only=True)
    customer_name = serializers.CharField(source='customer.name', read_only=True)
    vendor_name = serializers.CharField(source='vendor.company_name', read_only=True)
    product_name = serializers.CharField(source='product.name', read_only=True)
    amount = serializers.DecimalField(max_digits=15, decimal_places=2, read_only=True)
    is_debit = serializers.BooleanField(read_only=True)
    
    class Meta:
        model = JournalEntryLine
        fields = [
            'id', 'line_number', 'account', 'account_code', 'account_name',
            'description', 'debit_amount', 'credit_amount', 'amount', 'is_debit',
            'base_currency_debit_amount', 'base_currency_credit_amount',
            'customer', 'customer_name', 'vendor', 'vendor_name',
            'product', 'product_name', 'project', 'department', 'location',
            'tax_code', 'tax_amount', 'quantity', 'unit_cost'
        ]
    
    def validate(self, data):
        """Validate journal entry line"""
        debit = data.get('debit_amount', 0)
        credit = data.get('credit_amount', 0)
        
        if debit and credit:
            raise serializers.ValidationError("A line cannot have both debit and credit amounts")
        if not debit and not credit:
            raise serializers.ValidationError("A line must have either debit or credit amount")
        
        return data


class JournalEntrySerializer(BaseFinanceSerializer):
    """Detailed serializer for Journal Entry"""
    
    journal_lines = JournalEntryLineSerializer(many=True)
    is_balanced = serializers.SerializerMethodField()
    posted_by_name = serializers.CharField(source='posted_by.get_full_name', read_only=True)
    approved_by_name = serializers.CharField(source='approved_by.get_full_name', read_only=True)
    
    class Meta:
        model = JournalEntry
        fields = [
            'id', 'entry_number', 'reference_number', 'entry_date',
            'status', 'entry_type', 'description', 'notes',
            'source_document_type', 'source_document_id', 'source_document_number',
            'total_debit', 'total_credit', 'is_balanced',
            'currency', 'exchange_rate', 'base_currency_total_debit',
            'base_currency_total_credit', 'created_by', 'posted_by',
            'posted_by_name', 'posted_date', 'approved_by', 'approved_by_name',
            'approved_date', 'reversed_entry', 'reversal_reason',
            'financial_period', 'attachments', 'journal_lines',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'entry_number', 'total_debit', 'total_credit',
            'base_currency_total_debit', 'base_currency_total_credit',
            'is_balanced', 'posted_by', 'posted_by_name', 'posted_date',
            'approved_by', 'approved_by_name', 'approved_date',
            'reversed_entry', 'created_at', 'updated_at'
        ]
    
    def get_is_balanced(self, obj):
        """Check if journal entry is balanced"""
        return abs(obj.total_debit - obj.total_credit) < 0.01
    
    @transaction.atomic
    def create(self, validated_data):
        """Create journal entry with lines"""
        lines_data = validated_data.pop('journal_lines')
        journal_entry = JournalEntry.objects.create(**validated_data)
        
        for line_data in lines_data:
            JournalEntryLine.objects.create(
                journal_entry=journal_entry,
                **line_data
            )
        
        journal_entry.calculate_totals()
        return journal_entry
    
    @transaction.atomic
    def update(self, instance, validated_data):
        """Update journal entry with lines"""
        if instance.status == 'POSTED':
            raise serializers.ValidationError("Cannot modify posted journal entries")
        
        lines_data = validated_data.pop('journal_lines', None)
        
        # Update journal entry
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        
        # Update lines if provided
        if lines_data is not None:
            instance.journal_lines.all().delete()
            for line_data in lines_data:
                JournalEntryLine.objects.create(
                    journal_entry=instance,
                    **line_data
                )
        
        instance.calculate_totals()
        return instance


class JournalEntryListSerializer(BaseFinanceSerializer):
    """Lightweight serializer for Journal Entry lists"""
    
    is_balanced = serializers.SerializerMethodField()
    line_count = serializers.SerializerMethodField()
    
    class Meta:
        model = JournalEntry
        fields = [
            'id', 'entry_number', 'entry_date', 'status', 'entry_type',
            'description', 'total_debit', 'total_credit', 'is_balanced',
            'line_count', 'currency', 'created_at'
        ]
    
    def get_is_balanced(self, obj):
        return abs(obj.total_debit - obj.total_credit) < 0.01
    
    def get_line_count(self, obj):
        return obj.journal_lines.count()


class JournalEntryCreateSerializer(serializers.Serializer):
    """Serializer for creating journal entries"""
    
    entry_date = serializers.DateField()
    entry_type = serializers.ChoiceField(choices=JournalEntry.ENTRY_TYPE_CHOICES)
    description = serializers.CharField(max_length=500)
    reference_number = serializers.CharField(max_length=100, required=False)
    notes = serializers.CharField(required=False)
    lines = JournalEntryLineSerializer(many=True)
    
    def validate_lines(self, value):
        """Validate journal entry lines balance"""
        total_debit = sum(line.get('debit_amount', 0) for line in value)
        total_credit = sum(line.get('credit_amount', 0) for line in value)
        
        if abs(total_debit - total_credit) > 0.01:
            raise serializers.ValidationError("Journal entry must be balanced")
        
        return value


class JournalEntryPostSerializer(serializers.Serializer):
    """Serializer for posting journal entries"""
    
    entry_ids = serializers.ListField(
        child=serializers.IntegerField(),
        min_length=1
    )
    post_date = serializers.DateField(required=False)
    notes = serializers.CharField(required=False)