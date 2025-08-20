# backend/apps/finance/viewsets/journal.py

from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db import transaction
from django_filters.rest_framework import DjangoFilterBackend
from django.shortcuts import get_object_or_404
from ..models import JournalEntry, JournalEntryLine
from ..serializers import (
    JournalEntrySerializer, JournalEntryListSerializer,
    JournalEntryCreateSerializer, JournalEntryPostSerializer
)
from ..services.journal_entry import JournalEntryService
from .base import BaseFinanceViewSet

class JournalEntryViewSet(BaseFinanceViewSet):
    """ViewSet for Journal Entries"""
    
    queryset = JournalEntry.objects.select_related(
        'currency', 'created_by', 'posted_by', 'approved_by'
    ).prefetch_related('journal_lines__account')
    
    filterset_fields = ['status', 'entry_type', 'entry_date', 'currency']
    search_fields = ['entry_number', 'description', 'reference_number']
    ordering_fields = ['entry_date', 'entry_number', 'total_debit', 'created_at']
    ordering = ['-entry_date', '-entry_number']
    
    def get_serializer_class(self):
        """Return appropriate serializer based on action"""
        if self.action == 'list':
            return JournalEntryListSerializer
        elif self.action in ['create_entry', 'create']:
            return JournalEntryCreateSerializer
        elif self.action == 'post_entries':
            return JournalEntryPostSerializer
        return JournalEntrySerializer
    
    @transaction.atomic
    @action(detail=False, methods=['post'])
    def create_entry(self, request):
        """Create a new journal entry with validation"""
        serializer = JournalEntryCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        service = JournalEntryService(request.tenant)
        try:
            journal_entry = service.create_manual_entry(
                entry_date=serializer.validated_data['entry_date'],
                entry_type=serializer.validated_data['entry_type'],
                description=serializer.validated_data['description'],
                lines_data=serializer.validated_data['lines'],
                reference_number=serializer.validated_data.get('reference_number'),
                notes=serializer.validated_data.get('notes'),
                user=request.user
            )
            
            response_serializer = JournalEntrySerializer(journal_entry)
            return Response(response_serializer.data, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @transaction.atomic
    @action(detail=True, methods=['post'])
    def post_entry(self, request, pk=None):
        """Post a journal entry"""
        journal_entry = self.get_object()
        
        if journal_entry.status == 'POSTED':
            return Response(
                {'error': 'Journal entry is already posted'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            journal_entry.post_entry(request.user)
            serializer = self.get_serializer(journal_entry)
            return Response({
                'message': 'Journal entry posted successfully',
                'journal_entry': serializer.data
            })
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @transaction.atomic
    @action(detail=False, methods=['post'])
    def post_entries(self, request):
        """Post multiple journal entries"""
        serializer = JournalEntryPostSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        entry_ids = serializer.validated_data['entry_ids']
        posted_entries = []
        errors = []
        
        for entry_id in entry_ids:
            try:
                journal_entry = get_object_or_404(
                    self.get_queryset(),
                    id=entry_id
                )
                if journal_entry.status != 'POSTED':
                    journal_entry.post_entry(request.user)
                posted_entries.append(entry_id)
            except Exception as e:
                errors.append({
                    'entry_id': entry_id,
                    'error': str(e)
                })
        
        return Response({
            'posted_entries': posted_entries,
            'errors': errors,
            'message': f'Posted {len(posted_entries)} journal entries'
        })
    
    @transaction.atomic
    @action(detail=True, methods=['post'])
    def reverse_entry(self, request, pk=None):
        """Reverse a journal entry"""
        journal_entry = self.get_object()
        reason = request.data.get('reason', 'Entry reversal')
        
        if journal_entry.status != 'POSTED':
            return Response(
                {'error': 'Only posted entries can be reversed'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            reversal_entry = journal_entry.reverse_entry(request.user, reason)
            serializer = self.get_serializer(reversal_entry)
            return Response({
                'message': 'Journal entry reversed successfully',
                'reversal_entry': serializer.data
            })
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=False, methods=['get'])
    def trial_balance_entries(self, request):
        """Get journal entries for trial balance"""
        as_of_date = request.query_params.get('as_of_date')
        
        queryset = self.get_queryset().filter(status='POSTED')
        if as_of_date:
            queryset = queryset.filter(entry_date__lte=as_of_date)
        
        serializer = JournalEntryListSerializer(queryset, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def summary(self, request):
        """Get journal entries summary"""
        queryset = self.get_queryset()
        
        # Filter by date range if provided
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        
        if start_date:
            queryset = queryset.filter(entry_date__gte=start_date)
        if end_date:
            queryset = queryset.filter(entry_date__lte=end_date)
        
        # Calculate summary statistics
        from django.db.models import Sum, Count
        
        summary = queryset.aggregate(
            total_entries=Count('id'),
            total_debit=Sum('total_debit'),
            total_credit=Sum('total_credit'),
            posted_entries=Count('id', filter=Q(status='POSTED')),
            draft_entries=Count('id', filter=Q(status='DRAFT'))
        )
        
        return Response(summary)