# backend/apps/finance/views/journal_entries.py

"""
Journal Entry Management Views
"""

from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterFilter

from apps.core.permissions import IsTenantUser
from ..models import JournalEntry, JournalEntryLine
from ..serializers.journal import (
    JournalEntrySerializer, JournalEntryCreateSerializer
)
from ..filters import JournalEntryFilter


class JournalEntryViewSet(viewsets.ModelViewSet):
    """Journal entry management"""
    
    permission_classes = [IsAuthenticated, IsTenantUser]
    filter_backends = [DjangoFilterFilter, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = JournalEntryFilter
    search_fields = ['entry_number', 'description', 'reference_number']
    ordering_fields = ['entry_date', 'entry_number', 'total_debit']
    ordering = ['-entry_date', '-entry_number']
    
    def get_queryset(self):
        return JournalEntry.objects.filter(
            tenant=self.request.tenant
        ).select_related('currency', 'created_by', 'posted_by').prefetch_related('journal_lines')
    
    def get_serializer_class(self):
        if self.action == 'create':
            return JournalEntryCreateSerializer
        return JournalEntrySerializer
    
    def perform_create(self, serializer):
        serializer.save(
            tenant=self.request.tenant,
            created_by=self.request.user
        )
    
    @action(detail=True, methods=['post'])
    def post(self, request, pk=None):
        """Post a journal entry"""
        journal_entry = self.get_object()
        
        if journal_entry.status == 'POSTED':
            return Response(
                {'error': 'Journal entry is already posted'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            journal_entry.post_entry(request.user)
            return Response({'message': 'Journal entry posted successfully'})
        except Exception as e:
            return Response(
                {'error': str(e)}, 
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=True, methods=['post'])
    def reverse(self, request, pk=None):
        """Reverse a journal entry"""
        journal_entry = self.get_object()
        reason = request.data.get('reason', '')
        
        if journal_entry.status != 'POSTED':
            return Response(
                {'error': 'Only posted entries can be reversed'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            reversal = journal_entry.reverse_entry(request.user, reason)
            serializer = JournalEntrySerializer(reversal, context={'request': request})
            return Response(serializer.data)
        except Exception as e:
            return Response(
                {'error': str(e)}, 
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=False, methods=['get'])
    def templates(self, request):
        """Get journal entry templates"""
        templates = [
            {
                'name': 'Cash Receipt',
                'type': 'RECEIPT',
                'lines': [
                    {'account_type': 'CURRENT_ASSET', 'debit': True},
                    {'account_type': 'REVENUE', 'credit': True}
                ]
            },
            {
                'name': 'Cash Payment',
                'type': 'PAYMENT',
                'lines': [
                    {'account_type': 'EXPENSE', 'debit': True},
                    {'account_type': 'CURRENT_ASSET', 'credit': True}
                ]
            },
            {
                'name': 'Depreciation',
                'type': 'DEPRECIATION',
                'lines': [
                    {'account_type': 'EXPENSE', 'debit': True},
                    {'account_type': 'FIXED_ASSET', 'credit': True}
                ]
            }
        ]
        return Response(templates)