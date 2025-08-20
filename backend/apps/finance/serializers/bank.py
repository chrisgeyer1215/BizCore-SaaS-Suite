# backend/apps/finance/serializers/bank.py

from rest_framework import serializers
from ..models import (
    BankAccount, BankStatement, BankTransaction, 
    BankReconciliation, ReconciliationAdjustment
)
from .base import BaseFinanceSerializer

class BankAccountSerializer(BaseFinanceSerializer):
    """Serializer for Bank Account"""
    
    account_name = serializers.CharField(source='account.name', read_only=True)
    account_code = serializers.CharField(source='account.code', read_only=True)
    
    class Meta:
        model = BankAccount
        fields = [
            'id', 'account', 'account_name', 'account_code', 'bank_name',
            'account_number', 'account_type', 'routing_number', 'swift_code',
            'iban', 'enable_bank_feeds', 'bank_feed_id', 'last_feed_sync',
            'statement_import_format', 'auto_reconcile',
            'reconciliation_tolerance', 'current_balance',
            'last_reconciled_balance', 'last_reconciliation_date',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'current_balance', 'last_reconciled_balance',
            'last_reconciliation_date', 'last_feed_sync',
            'created_at', 'updated_at'
        ]


class BankTransactionSerializer(BaseFinanceSerializer):
    """Serializer for Bank Transaction"""
    
    bank_statement_date = serializers.DateField(source='bank_statement.statement_date', read_only=True)
    matched_payment_number = serializers.CharField(
        source='matched_payment.payment_number', read_only=True
    )
    
    class Meta:
        model = BankTransaction
        fields = [
            'id', 'bank_statement', 'bank_statement_date', 'transaction_date',
            'post_date', 'transaction_type', 'amount', 'description',
            'memo', 'reference_number', 'check_number', 'payee',
            'bank_transaction_id', 'running_balance', 'reconciliation_status',
            'matched_payment', 'matched_payment_number', 'matched_journal_entry',
            'matched_transaction', 'reconciliation_difference',
            'reviewed_by', 'reviewed_date', 'review_notes', 'is_duplicate',
            'duplicate_of', 'match_confidence', 'matching_rule_applied',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'match_confidence', 'matching_rule_applied',
            'reviewed_by', 'reviewed_date', 'created_at', 'updated_at'
        ]


class BankStatementSerializer(BaseFinanceSerializer):
    """Serializer for Bank Statement"""
    
    bank_account_name = serializers.CharField(source='bank_account.bank_name', read_only=True)
    bank_transactions = BankTransactionSerializer(many=True, read_only=True)
    
    class Meta:
        model = BankStatement
        fields = [
            'id', 'bank_account', 'bank_account_name', 'statement_date',
            'statement_period_start', 'statement_period_end',
            'opening_balance', 'closing_balance', 'import_date',
            'imported_by', 'import_file_name', 'import_format',
            'imported_from', 'processing_status', 'total_transactions',
            'matched_transactions', 'unmatched_transactions',
            'is_reconciled', 'reconciled_date', 'reconciled_by',
            'bank_transactions', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'import_date', 'imported_by', 'processing_status',
            'total_transactions', 'matched_transactions',
            'unmatched_transactions', 'is_reconciled', 'reconciled_date',
            'reconciled_by', 'created_at', 'updated_at'
        ]


class ReconciliationAdjustmentSerializer(BaseFinanceSerializer):
    """Serializer for Reconciliation Adjustment"""
    
    class Meta:
        model = ReconciliationAdjustment
        fields = [
            'id', 'reconciliation', 'adjustment_type', 'amount',
            'description', 'bank_transaction', 'journal_entry',
            'is_processed', 'processed_date', 'processed_by',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'is_processed', 'processed_date', 'processed_by',
            'created_at', 'updated_at'
        ]


class BankReconciliationSerializer(BaseFinanceSerializer):
    """Serializer for Bank Reconciliation"""
    
    bank_account_name = serializers.CharField(source='bank_account.bank_name', read_only=True)
    adjustments = ReconciliationAdjustmentSerializer(many=True, read_only=True)
    reconciliation_summary = serializers.SerializerMethodField()
    
    class Meta:
        model = BankReconciliation
        fields = [
            'id', 'bank_account', 'bank_account_name', 'bank_statement',
            'reconciliation_date', 'previous_reconciliation_date',
            'statement_beginning_balance', 'statement_ending_balance',
            'book_beginning_balance', 'book_ending_balance',
            'total_deposits_in_transit', 'total_outstanding_checks',
            'total_bank_adjustments', 'total_book_adjustments',
            'adjusted_bank_balance', 'adjusted_book_balance',
            'difference', 'is_balanced', 'status', 'started_by',
            'started_date', 'completed_by', 'completed_date',
            'reviewed_by', 'reviewed_date', 'approved_by',
            'approved_date', 'notes', 'completion_notes',
            'auto_matched_count', 'manual_matched_count',
            'unmatched_count', 'reconciliation_summary',
            'adjustments', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'adjusted_bank_balance', 'adjusted_book_balance',
            'difference', 'is_balanced', 'started_by', 'started_date',
            'completed_by', 'completed_date', 'reviewed_by',
            'reviewed_date', 'approved_by', 'approved_date',
            'auto_matched_count', 'manual_matched_count',
            'unmatched_count', 'reconciliation_summary',
            'created_at', 'updated_at'
        ]
    
    def get_reconciliation_summary(self, obj):
        """Get reconciliation summary"""
        return obj.get_reconciliation_summary()