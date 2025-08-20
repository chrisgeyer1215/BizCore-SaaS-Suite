# backend/apps/finance/viewsets/accounts.py

from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Q
from ..models import AccountCategory, Account
from ..serializers import (
    AccountCategorySerializer, AccountSerializer, AccountListSerializer,
    AccountBalanceSerializer
)
from ..services.accounting import AccountingService
from .base import BaseFinanceViewSet

class AccountCategoryViewSet(BaseFinanceViewSet):
    """ViewSet for Account Categories"""
    
    queryset = AccountCategory.objects.all()
    serializer_class = AccountCategorySerializer
    filterset_fields = ['account_type', 'is_active']
    search_fields = ['name', 'description']
    ordering_fields = ['name', 'sort_order', 'account_type']
    ordering = ['account_type', 'sort_order', 'name']


class AccountViewSet(BaseFinanceViewSet):
    """ViewSet for Chart of Accounts"""
    
    queryset = Account.objects.select_related('category', 'parent_account', 'currency')
    filterset_fields = [
        'account_type', 'category', 'is_active', 'is_bank_account',
        'is_cash_account', 'parent_account'
    ]
    search_fields = ['code', 'name', 'description']
    ordering_fields = ['code', 'name', 'account_type', 'current_balance']
    ordering = ['code']
    
    def get_serializer_class(self):
        """Return appropriate serializer based on action"""
        if self.action == 'list':
            return AccountListSerializer
        return AccountSerializer
    
    @action(detail=False, methods=['get'])
    def balance_sheet_accounts(self, request):
        """Get accounts for balance sheet"""
        accounts = self.get_queryset().filter(
            account_type__in=[
                'ASSET', 'CURRENT_ASSET', 'FIXED_ASSET', 'OTHER_ASSET',
                'LIABILITY', 'CURRENT_LIABILITY', 'LONG_TERM_LIABILITY',
                'EQUITY', 'RETAINED_EARNINGS'
            ]
        ).order_by('account_type', 'code')
        
        serializer = AccountListSerializer(accounts, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def income_statement_accounts(self, request):
        """Get accounts for income statement"""
        accounts = self.get_queryset().filter(
            account_type__in=[
                'REVENUE', 'OTHER_INCOME', 'EXPENSE', 'COST_OF_GOODS_SOLD', 'OTHER_EXPENSE'
            ]
        ).order_by('account_type', 'code')
        
        serializer = AccountListSerializer(accounts, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def balance(self, request, pk=None):
        """Get account balance"""
        account = self.get_object()
        as_of_date = request.query_params.get('as_of_date')
        currency = request.query_params.get('currency')
        
        service = AccountingService(request.tenant)
        balance_data = service.get_account_balance(account.id, as_of_date, currency)
        
        serializer = AccountBalanceSerializer(data={
            'account_id': account.id,
            'as_of_date': as_of_date,
            'currency': currency,
            'balance': balance_data['balance'],
            'base_currency_balance': balance_data['base_currency_balance']
        })
        serializer.is_valid()
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def hierarchy(self, request):
        """Get account hierarchy tree"""
        accounts = self.get_queryset().filter(is_active=True)
        
        # Build hierarchy
        def build_tree(parent_id=None):
            children = accounts.filter(parent_account_id=parent_id).order_by('code')
            tree = []
            for account in children:
                node = {
                    'id': account.id,
                    'code': account.code,
                    'name': account.name,
                    'account_type': account.account_type,
                    'level': account.level,
                    'current_balance': account.current_balance,
                    'children': build_tree(account.id)
                }
                tree.append(node)
            return tree
        
        hierarchy = build_tree()
        return Response(hierarchy)
    
    @action(detail=False, methods=['post'])
    def bulk_create(self, request):
        """Bulk create accounts from chart of accounts template"""
        accounts_data = request.data.get('accounts', [])
        created_accounts = []
        
        for account_data in accounts_data:
            account_data['tenant'] = request.tenant.id
            serializer = AccountSerializer(data=account_data)
            if serializer.is_valid():
                account = serializer.save(
                    tenant=request.tenant,
                    created_by=request.user
                )
                created_accounts.append(account)
        
        serializer = AccountListSerializer(created_accounts, many=True)
        return Response(serializer.data, status=status.HTTP_201_CREATED)