# crm/viewsets/base.py
"""
Base ViewSet Classes for CRM Module

Provides foundational ViewSet classes and mixins that include:
- Tenant-aware data access
- Permission handling
- Common CRUD operations
- Bulk operation support
- Analytics capabilities
- Export functionality
- Advanced filtering and search
"""

from typing import Dict, Any, List, Optional
from django.db.models import QuerySet, Q
from django.http import HttpResponse
from django.utils import timezone
from django.core.cache import cache
from django.db import transaction

from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.pagination import PageNumberPagination
from django_filters.rest_framework import DjangoFilterBackend

from crm.permissions.base import TenantPermission, CRMBasePermission
from crm.utils.tenant_utils import get_tenant_from_request, check_tenant_limits
from crm.utils.export_utils import CRMDataExporter, ExportConfiguration
from crm.utils.import_utils import CRMDataImporter, ImportConfiguration
from crm.utils.helpers import generate_reference_number, sanitize_input


class CRMPagination(PageNumberPagination):
    """
    Custom pagination for CRM ViewSets.
    """
    page_size = 25
    page_size_query_param = 'page_size'
    max_page_size = 100
    
    def get_paginated_response(self, data):
        """Enhanced paginated response with metadata."""
        return Response({
            'pagination': {
                'page': self.page.number,
                'pages': self.page.paginator.num_pages,
                'per_page': self.page_size,
                'total': self.page.paginator.count,
                'links': {
                    'next': self.get_next_link(),
                    'previous': self.get_previous_link()
                }
            },
            'data': data
        })


class TenantFilterMixin:
    """
    Mixin to ensure all queries are filtered by tenant.
    """
    
    def get_queryset(self):
        """Filter queryset by tenant."""
        queryset = super().get_queryset()
        tenant = get_tenant_from_request(self.request)
        
        if tenant and hasattr(queryset.model, 'tenant'):
            return queryset.filter(tenant=tenant)
        
        return queryset
    
    def perform_create(self, serializer):
        """Automatically set tenant on creation."""
        tenant = get_tenant_from_request(self.request)
        if tenant and hasattr(serializer.Meta.model, 'tenant'):
            serializer.save(tenant=tenant)
        else:
            serializer.save()


class BulkOperationMixin:
    """
    Mixin for bulk operations (create, update, delete).
    """
    
    @action(detail=False, methods=['post'])
    def bulk_create(self, request):
        """
        Bulk create multiple records.
        
        Expected payload:
        {
            "data": [
                {"field1": "value1", "field2": "value2"},
                {"field1": "value3", "field2": "value4"}
            ]
        }
        """
        try:
            data_list = request.data.get('data', [])
            if not isinstance(data_list, list):
                return Response(
                    {'error': 'Data must be a list'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Check tenant limits
            tenant = get_tenant_from_request(request)
            if tenant:
                resource_type = self.get_resource_type()
                limit_check = check_tenant_limits(tenant, resource_type, len(data_list))
                if not limit_check['allowed']:
                    return Response(
                        {'error': limit_check['error']},
                        status=status.HTTP_403_FORBIDDEN
                    )
            
            created_objects = []
            errors = []
            
            with transaction.atomic():
                for i, item_data in enumerate(data_list):
                    try:
                        serializer = self.get_serializer(data=item_data)
                        if serializer.is_valid():
                            obj = serializer.save()
                            created_objects.append(serializer.data)
                        else:
                            errors.append({
                                'index': i,
                                'data': item_data,
                                'errors': serializer.errors
                            })
                    except Exception as e:
                        errors.append({
                            'index': i,
                            'data': item_data,
                            'errors': str(e)
                        })
            
            return Response({
                'created': len(created_objects),
                'failed': len(errors),
                'data': created_objects,
                'errors': errors
            }, status=status.HTTP_201_CREATED if created_objects else status.HTTP_400_BAD_REQUEST)
        
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['patch'])
    def bulk_update(self, request):
        """
        Bulk update multiple records.
        
        Expected payload:
        {
            "data": [
                {"id": 1, "field1": "new_value1"},
                {"id": 2, "field1": "new_value2"}
            ]
        }
        """
        try:
            data_list = request.data.get('data', [])
            if not isinstance(data_list, list):
                return Response(
                    {'error': 'Data must be a list'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            updated_objects = []
            errors = []
            
            with transaction.atomic():
                for i, item_data in enumerate(data_list):
                    try:
                        obj_id = item_data.get('id')
                        if not obj_id:
                            errors.append({
                                'index': i,
                                'data': item_data,
                                'errors': 'ID is required for updates'
                            })
                            continue
                        
                        obj = self.get_queryset().get(id=obj_id)
                        serializer = self.get_serializer(obj, data=item_data, partial=True)
                        
                        if serializer.is_valid():
                            serializer.save()
                            updated_objects.append(serializer.data)
                        else:
                            errors.append({
                                'index': i,
                                'data': item_data,
                                'errors': serializer.errors
                            })
                    except self.queryset.model.DoesNotExist:
                        errors.append({
                            'index': i,
                            'data': item_data,
                            'errors': f'Object with ID {obj_id} not found'
                        })
                    except Exception as e:
                        errors.append({
                            'index': i,
                            'data': item_data,
                            'errors': str(e)
                        })
            
            return Response({
                'updated': len(updated_objects),
                'failed': len(errors),
                'data': updated_objects,
                'errors': errors
            }, status=status.HTTP_200_OK)
        
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['delete'])
    def bulk_delete(self, request):
        """
        Bulk delete multiple records.
        
        Expected payload:
        {
            "ids": [1, 2, 3, 4, 5]
        }
        """
        try:
            ids = request.data.get('ids', [])
            if not isinstance(ids, list):
                return Response(
                    {'error': 'IDs must be a list'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            deleted_count = 0
            errors = []
            
            with transaction.atomic():
                for obj_id in ids:
                    try:
                        obj = self.get_queryset().get(id=obj_id)
                        obj.delete()
                        deleted_count += 1
                    except self.queryset.model.DoesNotExist:
                        errors.append(f'Object with ID {obj_id} not found')
                    except Exception as e:
                        errors.append(f'Error deleting ID {obj_id}: {str(e)}')
            
            return Response({
                'deleted': deleted_count,
                'failed': len(errors),
                'errors': errors
            }, status=status.HTTP_200_OK)
        
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def get_resource_type(self) -> str:
        """Get resource type for tenant limit checking."""
        model_name = self.queryset.model.__name__.lower()
        return model_name


class ExportMixin:
    """
    Mixin for data export functionality.
    """
    
    @action(detail=False, methods=['post'])
    def export(self, request):
        """
        Export data in various formats.
        
        Expected payload:
        {
            "format": "csv|excel|json|pdf",
            "filters": {},
            "fields": [],
            "filename": "optional_filename"
        }
        """
        try:
            export_format = request.data.get('format', 'csv')
            filters = request.data.get('filters', {})
            fields = request.data.get('fields', [])
            filename = request.data.get('filename')
            
            # Apply filters to queryset
            queryset = self.filter_queryset(self.get_queryset())
            
            # Additional filters
            if filters:
                filter_q = Q()
                for field_name, field_value in filters.items():
                    if hasattr(queryset.model, field_name):
                        filter_q &= Q(**{field_name: field_value})
                queryset = queryset.filter(filter_q)
            
            # Configure export
            config = ExportConfiguration(
                format=export_format,
                include_headers=True,
                include_metadata=True,
                batch_size=1000
            )
            
            if fields:
                # Create field mapping for selected fields
                config.field_mapping = {field: field for field in fields}
            
            # Export data
            exporter = CRMDataExporter(get_tenant_from_request(request))
            
            if not filename:
                filename = f"{queryset.model.__name__.lower()}_export"
            
            return exporter.export_queryset(queryset, config, filename)
        
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['post'])
    def import_data(self, request):
        """
        Import data from uploaded file.
        
        Expected: Multipart form data with 'file' field
        """
        try:
            if 'file' not in request.FILES:
                return Response(
                    {'error': 'File is required'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            uploaded_file = request.FILES['file']
            file_format = request.data.get('format', 'csv')
            
            # Configure import
            config = ImportConfiguration(
                source_format=file_format,
                target_model=self.queryset.model.__name__.lower(),
                duplicate_handling='skip',
                skip_errors=True,
                batch_size=100
            )
            
            # Import data
            importer = CRMDataImporter(get_tenant_from_request(request))
            result = importer.import_data(uploaded_file, config)
            
            return Response({
                'import_id': result.import_id,
                'total_records': result.total_records,
                'successful_imports': result.successful_imports,
                'failed_imports': result.failed_imports,
                'skipped_records': result.skipped_records,
                'processing_time': result.processing_time,
                'errors': result.errors[:10]  # Return first 10 errors
            }, status=status.HTTP_200_OK)
        
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class AnalyticsMixin:
    """
    Mixin for analytics and reporting functionality.
    """
    
    @action(detail=False, methods=['get'])
    def analytics(self, request):
        """Get basic analytics for the model."""
        try:
            queryset = self.filter_queryset(self.get_queryset())
            
            # Date range filter
            date_from = request.query_params.get('date_from')
            date_to = request.query_params.get('date_to')
            
            if date_from:
                queryset = queryset.filter(created_at__gte=date_from)
            if date_to:
                queryset = queryset.filter(created_at__lte=date_to)
            
            # Basic counts
            total_count = queryset.count()
            
            # Time-based analytics
            from django.db.models import Count
            from django.db.models.functions import TruncMonth, TruncWeek, TruncDay
            
            grouping = request.query_params.get('group_by', 'month')
            
            if grouping == 'day':
                time_series = queryset.annotate(
                    period=TruncDay('created_at')
                ).values('period').annotate(
                    count=Count('id')
                ).order_by('period')
            elif grouping == 'week':
                time_series = queryset.annotate(
                    period=TruncWeek('created_at')
                ).values('period').annotate(
                    count=Count('id')
                ).order_by('period')
            else:  # month
                time_series = queryset.annotate(
                    period=TruncMonth('created_at')
                ).values('period').annotate(
                    count=Count('id')
                ).order_by('period')
            
            return Response({
                'total_count': total_count,
                'time_series': list(time_series),
                'model': queryset.model.__name__,
                'date_range': {
                    'from': date_from,
                    'to': date_to
                },
                'grouping': grouping
            })
        
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get'])
    def summary_stats(self, request):
        """Get summary statistics."""
        try:
            queryset = self.filter_queryset(self.get_queryset())
            
            # Calculate summary statistics
            stats = {
                'total': queryset.count(),
                'created_today': queryset.filter(
                    created_at__date=timezone.now().date()
                ).count(),
                'created_this_week': queryset.filter(
                    created_at__gte=timezone.now() - timezone.timedelta(days=7)
                ).count(),
                'created_this_month': queryset.filter(
                    created_at__gte=timezone.now().replace(day=1)
                ).count()
            }
            
            return Response(stats)
        
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class AdvancedFilterMixin:
    """
    Mixin for advanced filtering capabilities.
    """
    
    def filter_queryset(self, queryset):
        """Enhanced filtering with advanced options."""
        queryset = super().filter_queryset(queryset)
        
        # Advanced search across multiple fields
        search_query = self.request.query_params.get('q')
        if search_query:
            queryset = self.apply_advanced_search(queryset, search_query)
        
        # Date range filtering
        date_from = self.request.query_params.get('date_from')
        date_to = self.request.query_params.get('date_to')
        
        if date_from:
            queryset = queryset.filter(created_at__gte=date_from)
        if date_to:
            queryset = queryset.filter(created_at__lte=date_to)
        
        # Custom field filtering
        for param, value in self.request.query_params.items():
            if param.startswith('cf_'):  # Custom field prefix
                field_name = param[3:]  # Remove 'cf_' prefix
                queryset = self.apply_custom_field_filter(queryset, field_name, value)
        
        return queryset
    
    def apply_advanced_search(self, queryset, search_query):
        """Apply advanced search across multiple fields."""
        if not hasattr(self, 'search_fields'):
            return queryset
        
        search_q = Q()
        for field in self.search_fields:
            search_q |= Q(**{f"{field}__icontains": search_query})
        
        return queryset.filter(search_q)
    
    def apply_custom_field_filter(self, queryset, field_name, value):
        """Apply filtering for custom fields."""
        # This would implement custom field filtering
        # Implementation depends on how custom fields are stored
        return queryset


class CRMBaseViewSet(TenantFilterMixin, BulkOperationMixin, ExportMixin, 
                    AnalyticsMixin, AdvancedFilterMixin, viewsets.ModelViewSet):
    """
    Base ViewSet for all CRM models with comprehensive functionality.
    """
    
    permission_classes = [IsAuthenticated, TenantPermission]
    pagination_class = CRMPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    
    def get_permissions(self):
        """Get permissions with tenant awareness."""
        permissions = super().get_permissions()
        
        # Add model-specific permissions
        model_permission = self.get_model_permission()
        if model_permission:
            permissions.append(model_permission())
        
        return permissions
    
    def get_model_permission(self):
        """Get model-specific permission class."""
        # This can be overridden in subclasses
        return CRMBasePermission
    
    def perform_create(self, serializer):
        """Enhanced creation with audit logging."""
        super().perform_create(serializer)
        
        # Log creation
        self.log_action('create', serializer.instance)
    
    def perform_update(self, serializer):
        """Enhanced update with audit logging."""
        old_instance = serializer.instance
        super().perform_update(serializer)
        
        # Log update
        self.log_action('update', serializer.instance, old_instance)
    
    def perform_destroy(self, instance):
        """Enhanced deletion with audit logging."""
        self.log_action('delete', instance)
        super().perform_destroy(instance)
    
    def log_action(self, action, instance, old_instance=None):
        """Log user actions for audit purposes."""
        try:
            from crm.models.system import AuditTrail
            
            AuditTrail.objects.create(
                tenant=get_tenant_from_request(self.request),
                user=self.request.user,
                model=instance.__class__.__name__,
                object_id=instance.id,
                action=action,
                changes=self.get_change_details(instance, old_instance) if old_instance else None,
                ip_address=self.request.META.get('REMOTE_ADDR'),
                user_agent=self.request.META.get('HTTP_USER_AGENT')
            )
        except Exception as e:
            # Don't fail the request if audit logging fails
            print(f"Audit logging failed: {e}")
    
    def get_change_details(self, new_instance, old_instance):
        """Get details of changes made to instance."""
        changes = {}
        
        for field in new_instance._meta.fields:
            field_name = field.name
            old_value = getattr(old_instance, field_name, None)
            new_value = getattr(new_instance, field_name, None)
            
            if old_value != new_value:
                changes[field_name] = {
                    'old': str(old_value) if old_value is not None else None,
                    'new': str(new_value) if new_value is not None else None
                }
        
        return changes
    
    @action(detail=True, methods=['get'])
    def audit_trail(self, request, pk=None):
        """Get audit trail for specific object."""
        try:
            from crm.models.system import AuditTrail
            
            instance = self.get_object()
            audit_logs = AuditTrail.objects.filter(
                tenant=get_tenant_from_request(request),
                model=instance.__class__.__name__,
                object_id=instance.id
            ).order_by('-created_at')
            
            # Serialize audit logs
            audit_data = []
            for log in audit_logs:
                audit_data.append({
                    'id': log.id,
                    'action': log.action,
                    'user': str(log.user),
                    'changes': log.changes,
                    'timestamp': log.created_at.isoformat(),
                    'ip_address': log.ip_address
                })
            
            return Response({
                'object_id': instance.id,
                'model': instance.__class__.__name__,
                'audit_trail': audit_data
            })
        
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class CRMReadOnlyViewSet(TenantFilterMixin, ExportMixin, AnalyticsMixin, 
                        AdvancedFilterMixin, viewsets.ReadOnlyModelViewSet):
    """
    Read-only ViewSet for CRM models that don't need full CRUD.
    """
    
    permission_classes = [IsAuthenticated, TenantPermission]
    pagination_class = CRMPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]


# Utility decorators for ViewSets
def cache_response(timeout=300, key_func=None):
    """
    Decorator to cache ViewSet responses.
    
    Args:
        timeout: Cache timeout in seconds
        key_func: Function to generate cache key
    """
    def decorator(view_func):
        def wrapper(self, request, *args, **kwargs):
            # Generate cache key
            if key_func:
                cache_key = key_func(self, request, *args, **kwargs)
            else:
                tenant = get_tenant_from_request(request)
                cache_key = f"crm_{tenant.id if tenant else 'public'}_{self.__class__.__name__}_{view_func.__name__}_{hash(str(request.GET))}"
            
            # Try to get from cache
            cached_response = cache.get(cache_key)
            if cached_response:
                return Response(cached_response)
            
            # Execute view and cache response
            response = view_func(self, request, *args, **kwargs)
            if response.status_code == 200:
                cache.set(cache_key, response.data, timeout)
            
            return response
        return wrapper
    return decorator


def require_tenant_limits(resource_type, additional_usage=1):
    """
    Decorator to enforce tenant resource limits on ViewSet actions.
    """
    def decorator(view_func):
        def wrapper(self, request, *args, **kwargs):
            tenant = get_tenant_from_request(request)
            if tenant:
                limit_check = check_tenant_limits(tenant, resource_type, additional_usage)
                if not limit_check['allowed']:
                    return Response(
                        {
                            'error': limit_check['error'],
                            'current_usage': limit_check['current_usage'],
                            'limit': limit_check['limit']
                        },
                        status=status.HTTP_403_FORBIDDEN
                    )
            
            return view_func(self, request, *args, **kwargs)
        return wrapper
    return decorator