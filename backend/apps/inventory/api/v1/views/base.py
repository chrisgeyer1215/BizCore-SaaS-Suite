from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from django.db import transaction
from django.utils import timezone
from django.core.cache import cache
from typing import Dict, Any, List
import logging

from ....utils.exceptions import handle_inventory_exception
from ..permissions import InventoryPermission
from ..pagination import StandardResultsSetPagination
from ..filters import TenantFilterBackend

logger = logging.getLogger(__name__)

class BaseInventoryViewSet(viewsets.ModelViewSet):
    """
    Base ViewSet for all inventory models
    """
    permission_classes = [permissions.IsAuthenticated, InventoryPermission]
    pagination_class = StandardResultsSetPagination
    filter_backends = [TenantFilterBackend, DjangoFilterBackend, SearchFilter, OrderingFilter]
    
    def get_queryset(self):
        """Get tenant-filtered queryset"""
        queryset = super().get_queryset()
        
        # Apply tenant filtering
        if hasattr(self.get_serializer_class().Meta.model, 'tenant'):
            tenant = self.request.user.tenant  # Assuming user has tenant
            queryset = queryset.filter(tenant=tenant)
        
        return queryset
    
    def get_serializer_context(self):
        """Add tenant and user to serializer context"""
        context = super().get_serializer_context()
        context.update({
            'tenant': getattr(self.request.user, 'tenant', None),
            'user': self.request.user,
            'request': self.request
        })
        return context
    
    @handle_inventory_exception
    def create(self, request, *args, **kwargs):
        """Enhanced create with error handling"""
        return super().create(request, *args, **kwargs)
    
    @handle_inventory_exception
    def update(self, request, *args, **kwargs):
        """Enhanced update with error handling"""
        return super().update(request, *args, **kwargs)
    
    @handle_inventory_exception
    def destroy(self, request, *args, **kwargs):
        """Enhanced delete with error handling"""
        return super().destroy(request, *args, **kwargs)
    
    @action(detail=False, methods=['post'])
    def bulk_create(self, request):
        """Bulk create multiple objects"""
        try:
            data
                return Response(
                    {'error': 'No items provided'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            if len(data) > 1000:  # Configurable limit
                return Response(
                    {'error': 'Maximum 1000 items allowed per bulk operation'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            created_objects = []
            errors = []
            
            with transaction.atomic():
                for i, item_data in enumerate(data):
                    try:
                        serializer = self.get_serializer(data=item_data)
                        if serializer.is_valid():
                            obj = serializer.save()
                            created_objects.append({
                                'index': i,
                                'id': obj.id,
                                'data': serializer.data
                            })
                        else:
                            errors.append({
                                'index': i,
                                'errors': serializer.errors
                            })
                    except Exception as e:
                        errors.append({
                            'index': i,
                            'errors': {'non_field_errors': [str(e)]}
                        })
                
                if errors:
                    transaction.set_rollback(True)
                    return Response({
                        'success': False,
                        'message': 'Bulk create failed',
                        'errors': errors,
                        'created_count': 0
                    }, status=status.HTTP_400_BAD_REQUEST)
            
            return Response({
                'success': True,
                'message': f'Successfully created {len(created_objects)} objects',
                'created_count': len(created_objects),
                'created_objects': created_objects
            }, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            logger.error(f"Bulk create error: {str(e)}")
            return Response(
                {'error': 'Internal server error during bulk create'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['patch'])
    def bulk_update(self, request):
        """Bulk update multiple objects"""
        try:
            updates = request.data.get('updates', [])
            if not updates:
                return Response(
                    {'error': 'No updates provided'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            updated_objects = []
            errors = []
            
            with transaction.atomic():
                for i, update_data in enumerate(updates):
                    try:
                        obj_id = update_data.get('id')
                        if not obj_id:
                            errors.append({
                                'index': i,
                                'errors': {'id': ['This field is required']}
                            })
                            continue
                        
                        obj = self.get_queryset().get(id=obj_id)
                        serializer = self.get_serializer(
                            obj, data=update_data, partial=True
                        )
                        
                        if serializer.is_valid():
                            updated_obj = serializer.save()
                            updated_objects.append({
                                'index': i,
                                'id': updated_obj.id,
                                'data': serializer.data
                            })
                        else:
                            errors.append({
                                'index': i,
                                'errors': serializer.errors
                            })
                            
                    except self.get_serializer_class().Meta.model.DoesNotExist:
                        errors.append({
                            'index': i,
                            'errors': {'id': ['Object not found']}
                        })
                    except Exception as e:
                        errors.append({
                            'index': i,
                            'errors': {'non_field_errors': [str(e)]}
                        })
                
                if errors:
                    transaction.set_rollback(True)
                    return Response({
                        'success': False,
                        'message': 'Bulk update failed',
                        'errors': errors,
                        'updated_count': 0
                    }, status=status.HTTP_400_BAD_REQUEST)
            
            return Response({
                'success': True,
                'message': f'Successfully updated {len(updated_objects)} objects',
                'updated_count': len(updated_objects),
                'updated_objects': updated_objects
            })
            
        except Exception as e:
            logger.error(f"Bulk update error: {str(e)}")
            return Response(
                {'error': 'Internal server error during bulk update'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['delete'])
    def bulk_delete(self, request):
        """Bulk delete multiple objects"""
        try:
            ids = request.data.get('ids', [])
            if not ids:
                return Response(
                    {'error': 'No IDs provided'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            if len(ids) > 1000:
                return Response(
                    {'error': 'Maximum 1000 items allowed per bulk delete'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            with transaction.atomic():
                objects_to_delete = self.get_queryset().filter(id__in=ids)
                deleted_count = objects_to_delete.count()
                
                if deleted_count != len(ids):
                    return Response(
                        {'error': 'Some objects not found'},
                        status=status.HTTP_404_NOT_FOUND
                    )
                
                objects_to_delete.delete()
            
            return Response({
                'success': True,
                'message': f'Successfully deleted {deleted_count} objects',
                'deleted_count': deleted_count
            })
            
        except Exception as e:
            logger.error(f"Bulk delete error: {str(e)}")
            return Response(
                {'error': 'Internal server error during bulk delete'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get'])
    def export(self, request):
        """Export data in various formats"""
        try:
            export_format = request.query_params.get('format', 'csv').lower()
            
            if export_format not in ['csv', 'excel', 'json']:
                return Response(
                    {'error': 'Unsupported export format'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            queryset = self.filter_queryset(self.get_queryset())
            
            # Limit export size
            if queryset.count() > 10000:
                return Response(
                    {'error': 'Export limit exceeded (max 10,000 records)'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Generate export file (implementation would depend on format)
            # This would typically be handled by a background task
            from ....tasks.celery import generate_export_task
            
            task = generate_export_task.delay(
                model_name=self.get_serializer_class().Meta.model.__name__,
                tenant_id=request.user.tenant.id,
                filters=dict(request.query_params),
                format=export_format
            )
            
            return Response({
                'success': True,
                'message': 'Export started',
                'task_id': task.id
            })
            
        except Exception as e:
            logger.error(f"Export error: {str(e)}")
            return Response(
                {'error': 'Export failed'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class BaseInventoryAPIView(APIView):
    """
    Base API View for inventory operations
    """
    permission_classes = [permissions.IsAuthenticated, InventoryPermission]
    
    def get_tenant(self):
        """Get current user's tenant"""
        return getattr(self.request.user, 'tenant', None)
    
    def create_response(self, data=None, message="Success", success=True, status_code=status.HTTP_200_OK):
        """Create standardized API response"""
        return Response({
            'success': success,
            'message': message,
            'data': data,
            'timestamp': timezone.now()
        }, status=status_code)
    
    def create_error_response(self, message="Error", errors=None, status_code=status.HTTP_400_BAD_REQUEST):
        """Create standardized error response"""
        return Response({
            'success': False,
            'error': message,
            'errors': errors or {},
            'timestamp': timezone.now()
        }, status=status_code)
    
    @handle_inventory_exception
    def dispatch(self, request, *args, **kwargs):
        """Enhanced dispatch with error handling"""
        return super().dispatch(request, *args, **kwargs)

class CacheableAPIView(BaseInventoryAPIView):
    """
    API View with caching support
    """
    cache_timeout = 300  # 5 minutes default
    cache_key_prefix = 'api_cache'
    
    def get_cache_key(self, request, *args, **kwargs):
        """Generate cache key for the request"""
        tenant_id = self.get_tenant().id if self.get_tenant() else 'no_tenant'
        query_params = '&'.join([f"{k}={v}" for k, v in sorted(request.query_params.items())])
        path = request.path_info
        
        from hashlib import md5
        cache_key = f"{self.cache_key_prefix}:{tenant_id}:{path}:{md5(query_params.encode()).hexdigest()}"
        return cache_key
    
    def get_cached_response(self, request, *args, **kwargs):
        """Get cached response if available"""
        if request.method != 'GET':
            return None
        
        cache_key = self.get_cache_key(request, *args, **kwargs)
        return cache.get(cache_key)
    
    def set_cache_response(self, request, response, *args, **kwargs):
        """Cache the response"""
        if request.method == 'GET' and response.status_code == 200:
            cache_key = self.get_cache_key(request, *args, **kwargs)
            cache.set(cache_key, response.data, self.cache_timeout)
    
    def dispatch(self, request, *args, **kwargs):
        """Override dispatch to handle caching"""
        # Try to get cached response
        cached_response = self.get_cached_response(request, *args, **kwargs)
        if cached_response:
            return Response(cached_response)
        
        # Process request normally
        response = super().dispatch(request, *args, **kwargs)
        
        # Cache the response
        self.set_cache_response(request, response, *args, **kwargs)
        
        return response

class AsyncTaskAPIView(BaseInventoryAPIView):
    """
    API View for handling async tasks
    """
    
    def start_async_task(self, task_func, *args, **kwargs):
        """Start an async task and return task info"""
        try:
            task = task_func.delay(*args, **kwargs)
            return self.create_response(
                data={
                    'task_id': task.id,
                    'status': 'started',
                    'estimated_duration': '5-10 minutes'
                },
                message="Task started successfully"
            )
        except Exception as e:
            logger.error(f"Failed to start async task: {str(e)}")
            return self.create_error_response(
                "Failed to start task",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def get_task_status(self, task_id):
        """Get status of an async task"""
        try:
            from celery.result import AsyncResult
            
            task = AsyncResult(task_id)
            
            return self.create_response(data={
                'task_id': task_id,
                'status': task.status,
                'result': task.result if task.successful() else None,
                'error': str(task.result) if task.failed() else None
            })
            
        except Exception as e:
            logger.error(f"Failed to get task status: {str(e)}")
            return self.create_error_response("Failed to get task status")