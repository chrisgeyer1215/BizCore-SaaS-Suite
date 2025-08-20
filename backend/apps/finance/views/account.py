# backend/apps/finance/views/accounts.py

"""
Chart of Accounts Management Views
"""

from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterFilter
from django.db.models import Q

from apps.core.permissions import IsTenantUser
from ..models import AccountCategory, Account
from ..serializers.accounts import (
    AccountCategorySerializer, AccountSerializer, AccountTreeSerializer
)
from ..filters import AccountFilter


class AccountCategoryViewSet(viewsets.ModelViewSet):
    """Account category management"""
    
    permission_classes = [IsAuthenticated, IsTenantUser]
    serializer_class = AccountCategorySerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'description']
    ordering_fields = ['name', 'account_type', 'sort_order']
    ordering = ['account_type', 'sort_order', 'name']
    
    def get_queryset(self):
        return AccountCategory.objects.filter(
            tenant=self.request.tenant,
            is_active=True
        )


class AccountViewSet(viewsets.ModelViewSet):
    """Chart of accounts management"""
    
    permission_classes = [IsAuthenticated, IsTenantUser]
    serializer_class = AccountSerializer
    filter_backends = [DjangoFilterFilter, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = AccountFilter
    search_fields = ['code', 'name', 'description']
    ordering_fields = ['code', 'name', 'account_type', 'level']
    ordering = ['code']
    
    def get_queryset(self):
        return Account.objects.filter(
            tenant=self.request.tenant
        ).select_related('category', 'parent_account', 'currency')
    
    @action(detail=False, methods=['get'])
    def tree(self, request):
        """Get accounts in tree structure"""
        accounts = Account.objects.filter(
            tenant=request.tenant,
            parent_account__isnull=True,
            is_active=True
        ).order_by('code')
        
        serializer = AccountTreeSerializer(accounts, many=True, context={'request': request})
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def by_type(self, request):
        """Get accounts grouped by type"""
        account_type = request.query_params.get('type')
        if not account_type:
            return Response({'error': 'Account type is required'}, status=status.HTTP_400_BAD_REQUEST)
        
        accounts = Account.objects.filter(
            tenant=request.tenant,
            account_type=account_type,
            is_active=True
        ).order_by('code')
        
        serializer = AccountSerializer(accounts, many=True, context={'request': request})
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def balance(self, request, pk=None):
        """Get account balance"""
        account = self.get_object()
        as_of_date = request.query_params.get('as_of_date')
        
        from ..services.accounting import AccountingService
        service = AccountingService(request.tenant)
        
        balance = service.get_account_balance(
            account.id, 
            as_of_date=as_of_date
        )
        
        return Response({
            'account_id': account.id,
            'account_code': account.code,
            'account_name': account.name,
            'balance': float(balance),
            'as_of_date': as_of_date
        })
    
    @action(detail=False, methods=['post'])
    def import_chart(self, request):
        """Import chart of accounts from template"""
        template_type = request.data.get('template_type', 'standard')
        
        from ..services.accounting import AccountingService
        service = AccountingService(request.tenant)
        
        try:
            result = service.import_chart_of_accounts(template_type)
            return Response(result)
        except Exception as e:
            return Response(
                {'error': str(e)}, 
                status=status.HTTP_400_BAD_REQUEST
            )