# backend/apps/finance/viewsets/base.py

from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from apps.core.permissions import TenantPermission
from apps.core.pagination import StandardResultsSetPagination

class BaseFinanceViewSet(viewsets.ModelViewSet):
    """Base ViewSet for all finance models"""
    
    permission_classes = [permissions.IsAuthenticated, TenantPermission]
    pagination_class = StandardResultsSetPagination
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    
    def get_queryset(self):
        """Filter queryset by tenant"""
        return self.queryset.filter(tenant=self.request.tenant)
    
    def perform_create(self, serializer):
        """Add tenant and user to created objects"""
        serializer.save(
            tenant=self.request.tenant,
            created_by=self.request.user
        )
    
    def perform_update(self, serializer):
        """Add updated_by to modified objects"""
        serializer.save(updated_by=self.request.user)