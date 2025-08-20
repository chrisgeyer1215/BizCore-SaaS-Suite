# backend/apps/finance/viewsets/bank.py

from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db import transaction
from ..models import (
    BankAccount, BankStatement, BankTransaction, BankReconciliation
)
from ..serializers import (
    BankAccountSerializer, BankStatementSerializer, 
    BankTransactionSerializer, BankReconciliationSerializer
)
from ..services.bank_reconciliation import BankReconciliationService
from .base import BaseFinanceViewSet

class BankAccountViewSet(BaseFinanceViewSet):
    """ViewSet for Bank Accounts"""
    
    queryset = BankAccount.objects.select_related('account')
    filterset_fields = ['account_type', 'enable_bank_feeds', 'auto_reconcile']
    search_fields = ['bank_name', 'account_number', 'account__name']
    ordering_fields = ['bank_name', 'account_number', 'current_balance']
    ordering = ['bank_name']
    
    serializer_class = BankAccountSerializer
    
    @action(detail=True, methods=['get'])
    def statements(self, request, pk=None):
        """Get bank statements for account"""
        bank_account = self.get_object()
        statements = BankStatement.objects.filter(
            bank_account=bank_account,
            tenant=request.tenant
        ).order_by('-statement_date')
        
        serializer = BankStatementSerializer(statements, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def reconciliations(self, request, pk=None):
        """Get reconciliations for account"""
        bank_account = self.get_object()
        reconciliations = BankReconciliation.objects.filter(
            bank_account=bank_account,
            tenant=request.tenant
        ).order_by('-reconciliation_date')
        
        serializer = BankReconciliationSerializer(reconciliations, many=True)
        return Response(serializer.data)


class BankStatementViewSet(BaseFinanceViewSet):
    """ViewSet for Bank Statements"""
    
    queryset = BankStatement.objects.select_related('bank_account')
    filterset_fields = [
        'bank_account', 'processing_status', 'is_reconciled',
        'statement_date', 'import_format'
    ]
    search_fields = ['import_file_name', 'imported_from']
    ordering_fields = ['statement_date', 'import_date']
    ordering = ['-statement_date']
    
    serializer_class = BankStatementSerializer
    
    @action(detail=True, methods=['get'])
    def transactions(self, request, pk=None):
        """Get transactions for statement"""
        statement = self.get_object()
        transactions = BankTransaction.objects.filter(
            bank_statement=statement,
            tenant=request.tenant
        ).order_by('transaction_date', 'id')
        
        serializer = BankTransactionSerializer(transactions, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def auto_match_transactions(self, request, pk=None):
        """Auto-match transactions in statement"""
        statement = self.get_object()
        
        service = BankReconciliationService(request.tenant)
        try:
            results = service.auto_match_statement_transactions(statement)
            return Response({
                'message': 'Auto-matching completed',
                'matched_count': results['matched_count'],
                'unmatched_count': results['unmatched_count'],
                'results': results['details']
            })
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )


class BankReconciliationViewSet(BaseFinanceViewSet):
    """ViewSet for Bank Reconciliations"""
    
    queryset = BankReconciliation.objects.select_related(
        'bank_account', 'bank_statement'
    ).prefetch_related('adjustments')
    
    filterset_fields = ['bank_account', 'status', 'is_balanced', 'reconciliation_date']
    search_fields = ['bank_account__bank_name', 'notes']
    ordering_fields = ['reconciliation_date', 'started_date']
    ordering = ['-reconciliation_date']
    
    serializer_class = BankReconciliationSerializer
    
    @transaction.atomic
    @action(detail=False, methods=['post'])
    def start_reconciliation(self, request):
        """Start a new bank reconciliation"""
        bank_account_id = request.data.get('bank_account_id')
        bank_statement_id = request.data.get('bank_statement_id')
        
        service = BankReconciliationService(request.tenant)
        try:
            reconciliation = service.start_reconciliation(
                bank_account_id=bank_account_id,
                bank_statement_id=bank_statement_id,
                user=request.user
            )
            
            serializer = self.get_serializer(reconciliation)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @transaction.atomic
    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        """Complete bank reconciliation"""
        reconciliation = self.get_object()
        
        try:
            reconciliation.complete_reconciliation(request.user)
            serializer = self.get_serializer(reconciliation)
            return Response({
                'message': 'Reconciliation completed successfully',
                'reconciliation': serializer.data
            })
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )