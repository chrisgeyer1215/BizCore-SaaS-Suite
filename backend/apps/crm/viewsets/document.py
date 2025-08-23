"""
CRM Document ViewSets - Document Management System
Handles file uploads, sharing, categorization, and version control
"""

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser
from django.db.models import Q, Count
from django.http import HttpResponse
from django.utils import timezone
import mimetypes
import os

from ..models import Document, DocumentCategory, DocumentShare
from ..serializers.document import (
    DocumentSerializer, DocumentCategorySerializer,
    DocumentShareSerializer
)
from ..permissions.document import (
    CanViewDocuments, CanManageDocuments,
    CanShareDocuments, CanDeleteDocuments
)
from ..services.document_service import DocumentService
from ..utils.tenant_utils import get_tenant_context


class DocumentViewSet(viewsets.ModelViewSet):
    """
    Document Management ViewSet
    Handles file uploads, downloads, and document lifecycle
    """
    serializer_class = DocumentSerializer
    permission_classes = [IsAuthenticated, CanViewDocuments]
    parser_classes = [MultiPartParser, FormParser]
    
    def get_queryset(self):
        tenant = get_tenant_context(self.request)
        queryset = Document.objects.filter(
            tenant=tenant,
            is_deleted=False
        ).select_related('category', 'uploaded_by')
        
        # Filter by category
        category = self.request.query_params.get('category')
        if category:
            queryset = queryset.filter(category_id=category)
        
        # Filter by entity
        entity_type = self.request.query_params.get('entity_type')
        entity_id = self.request.query_params.get('entity_id')
        if entity_type and entity_id:
            queryset = queryset.filter(
                entity_type=entity_type,
                entity_id=entity_id
            )
        
        # Search functionality
        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) |
                Q(description__icontains=search) |
                Q(tags__icontains=search)
            )
        
        return queryset.order_by('-created_at')
    
    def perform_create(self, serializer):
        tenant = get_tenant_context(self.request)
        serializer.save(
            tenant=tenant,
            uploaded_by=self.request.user
        )
    
    def get_permissions(self):
        """Set permissions based on action"""
        if self.action in ['create', 'update', 'partial_update']:
            permission_classes = [IsAuthenticated, CanManageDocuments]
        elif self.action == 'destroy':
            permission_classes = [IsAuthenticated, CanDeleteDocuments]
        else:
            permission_classes = [IsAuthenticated, CanViewDocuments]
        
        return [permission() for permission in permission_classes]
    
    @action(detail=True, methods=['get'])
    def download(self, request, pk=None):
        """Download document file"""
        document = self.get_object()
        
        try:
            # Check if user has access to this document
            service = DocumentService(tenant=document.tenant)
            if not service.can_access_document(document, request.user):
                return Response({
                    'success': False,
                    'error': 'Access denied'
                }, status=status.HTTP_403_FORBIDDEN)
            
            # Log download activity
            service.log_document_access(
                document=document,
                user=request.user,
                action='download'
            )
            
            # Serve file
            file_path = document.file.path
            if os.path.exists(file_path):
                with open(file_path, 'rb') as file:
                    response = HttpResponse(
                        file.read(),
                        content_type=mimetypes.guess_type(file_path)[0] or 'application/octet-stream'
                    )
                    response['Content-Disposition'] = f'attachment; filename="{document.name}"'
                    return response
            else:
                return Response({
                    'success': False,
                    'error': 'File not found'
                }, status=status.HTTP_404_NOT_FOUND)
                
        except Exception as e:
            return Response({
                'success': False,
                'error': f"Download failed: {str(e)}"
            }, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['post'])
    def share(self, request, pk=None):
        """Share document with users or teams"""
        document = self.get_object()
        
        try:
            service = DocumentService(tenant=document.tenant)
            share_result = service.share_document(
                document=document,
                shared_by=request.user,
                share_with_users=request.data.get('users', []),
                share_with_teams=request.data.get('teams', []),
                permission_level=request.data.get('permission_level', 'view'),
                message=request.data.get('message', ''),
                expires_at=request.data.get('expires_at')
            )
            
            return Response({
                'success': True,
                'shares_created': len(share_result['shares']),
                'notifications_sent': share_result['notifications_sent'],
                'share_url': share_result.get('share_url')
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'error': f"Sharing failed: {str(e)}"
            }, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['get'])
    def versions(self, request, pk=None):
        """Get document version history"""
        document = self.get_object()
        
        versions = Document.objects.filter(
            tenant=document.tenant,
            parent_document=document
        ).order_by('-version')
        
        serializer = DocumentSerializer(versions, many=True)
        
        return Response({
            'success': True,
            'versions': serializer.data,
            'current_version': document.version,
            'total_versions': versions.count() + 1  # +1 for original
        })
    
    @action(detail=True, methods=['post'])
    def create_version(self, request, pk=None):
        """Create new version of document"""
        document = self.get_object()
        
        try:
            service = DocumentService(tenant=document.tenant)
            new_version = service.create_document_version(
                original_document=document,
                file=request.FILES.get('file'),
                version_notes=request.data.get('version_notes', ''),
                user=request.user
            )
            
            serializer = DocumentSerializer(new_version)
            
            return Response({
                'success': True,
                'new_version': serializer.data,
                'version_number': new_version.version,
                'message': 'New version created successfully'
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'error': f"Version creation failed: {str(e)}"
            }, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['get'])
    def preview(self, request, pk=None):
        """Generate document preview"""
        document = self.get_object()
        
        try:
            service = DocumentService(tenant=document.tenant)
            preview_data = service.generate_preview(
                document=document,
                user=request.user
            )
            
            return Response({
                'success': True,
                'preview_url': preview_data.get('preview_url'),
                'preview_type': preview_data.get('preview_type'),
                'thumbnail_url': preview_data.get('thumbnail_url'),
                'can_preview': preview_data.get('can_preview', False)
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'error': f"Preview generation failed: {str(e)}"
            }, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['post'])
    def bulk_upload(self, request):
        """Upload multiple documents"""
        try:
            service = DocumentService(tenant=get_tenant_context(request))
            results = service.bulk_upload_documents(
                files=request.FILES.getlist('files'),
                category_id=request.data.get('category_id'),
                entity_type=request.data.get('entity_type'),
                entity_id=request.data.get('entity_id'),
                tags=request.data.get('tags', ''),
                user=request.user
            )
            
            return Response({
                'success': True,
                'uploaded_count': results['uploaded_count'],
                'failed_count': results['failed_count'],
                'documents': results['documents'],
                'errors': results['errors']
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'error': f"Bulk upload failed: {str(e)}"
            }, status=status.HTTP_400_BAD_REQUEST)


class DocumentCategoryViewSet(viewsets.ModelViewSet):
    """
    Document Category Management ViewSet
    Handles document categorization and organization
    """
    serializer_class = DocumentCategorySerializer
    permission_classes = [IsAuthenticated, CanManageDocuments]
    
    def get_queryset(self):
        tenant = get_tenant_context(self.request)
        return DocumentCategory.objects.filter(
            tenant=tenant,
            is_active=True
        ).annotate(
            document_count=Count('documents')
        ).order_by('name')
    
    def perform_create(self, serializer):
        tenant = get_tenant_context(self.request)
        serializer.save(
            tenant=tenant,
            created_by=self.request.user
        )
    
    @action(detail=True, methods=['get'])
    def documents(self, request, pk=None):
        """Get all documents in this category"""
        category = self.get_object()
        
        documents = Document.objects.filter(
            category=category,
            is_deleted=False
        ).select_related('uploaded_by')
        
        serializer = DocumentSerializer(documents, many=True)
        
        return Response({
            'success': True,
            'documents': serializer.data,
            'total_count': documents.count()
        })


class DocumentShareViewSet(viewsets.ModelViewSet):
    """
    Document Share Management ViewSet
    Handles document sharing and access control
    """
    serializer_class = DocumentShareSerializer
    permission_classes = [IsAuthenticated, CanShareDocuments]
    
    def get_queryset(self):
        tenant = get_tenant_context(self.request)
        user = self.request.user
        
        # Users can see shares they created or shares where they are the recipient
        return DocumentShare.objects.filter(
            tenant=tenant,
            is_active=True
        ).filter(
            Q(shared_by=user) | Q(shared_with=user)
        ).select_related('document', 'shared_by', 'shared_with')
    
    def perform_create(self, serializer):
        tenant = get_tenant_context(self.request)
        serializer.save(
            tenant=tenant,
            shared_by=self.request.user
        )
    
    @action(detail=True, methods=['post'])
    def revoke(self, request, pk=None):
        """Revoke document share"""
        share = self.get_object()
        
        try:
            service = DocumentService(tenant=share.tenant)
            service.revoke_document_share(
                share=share,
                revoked_by=request.user
            )
            
            return Response({
                'success': True,
                'message': 'Document share revoked successfully'
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'error': f"Share revocation failed: {str(e)}"
            }, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['get'])
    def shared_with_me(self, request):
        """Get documents shared with current user"""
        tenant = get_tenant_context(request)
        user = request.user
        
        shares = DocumentShare.objects.filter(
            tenant=tenant,
            shared_with=user,
            is_active=True
        ).select_related('document', 'shared_by')
        
        serializer = DocumentShareSerializer(shares, many=True)
        
        return Response({
            'success': True,
            'shared_documents': serializer.data,
            'total_count': shares.count()
        })