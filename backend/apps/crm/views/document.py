# ============================================================================
# backend/apps/crm/views/document.py - Document Management Views
# ============================================================================

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.db.models import Q, Count, Sum, Avg, F, Case, When, Max
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.urls import reverse_lazy
from django.http import JsonResponse, HttpResponse, Http404, FileResponse
from django.views import View
from django.db import transaction
from django.utils import timezone
from django.contrib.contenttypes.models import ContentType
from django.core.paginator import Paginator
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from django.conf import settings
from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from datetime import datetime, timedelta
import os
import json
import mimetypes
import zipfile
from io import BytesIO

from .base import CRMBaseMixin, CRMBaseViewSet
from ..models import (
    Document, DocumentCategory, DocumentShare,
    Lead, Account, Contact, Opportunity, Team
)
from ..serializers import (
    DocumentSerializer, DocumentDetailSerializer, DocumentCategorySerializer,
    DocumentShareSerializer
)
from ..filters import DocumentFilter
from ..permissions import DocumentPermission
from ..services import DocumentService, NotificationService


class DocumentDashboardView(CRMBaseMixin, View):
    """Document management dashboard"""
    
    def get(self, request):
        user = request.user
        
        # Get documents based on user permissions
        documents = Document.objects.filter(
            tenant=request.tenant,
            is_active=True
        ).select_related('category', 'owner', 'content_type')
        
        # Filter by user access
        if not user.has_perm('crm.view_all_documents'):
            documents = documents.filter(
                Q(owner=user) |
                Q(access_level='PUBLIC') |
                Q(shares__user=user)
            ).distinct()
        
        # Dashboard statistics
        dashboard_stats = self.get_dashboard_stats(documents, user)
        
        # Recent documents
        recent_documents = documents.order_by('-created_at')[:10]
        
        # Most accessed documents
        popular_documents = documents.filter(
            view_count__gt=0
        ).order_by('-view_count')[:10]
        
        # My documents
        my_documents = documents.filter(owner=user).order_by('-created_at')[:10]
        
        # Shared with me
        shared_with_me = documents.filter(
            shares__user=user,
            shares__is_active=True
        ).order_by('-created_at')[:10]
        
        # Documents by category
        category_stats = self.get_category_stats(documents)
        
        # Storage analytics
        storage_stats = self.get_storage_stats(documents)
        
        # Recent activity
        recent_activity = self.get_recent_activity(documents)
        
        context = {
            'dashboard_stats': dashboard_stats,
            'recent_documents': recent_documents,
            'popular_documents': popular_documents,
            'my_documents': my_documents,
            'shared_with_me': shared_with_me,
            'category_stats': category_stats,
            'storage_stats': storage_stats,
            'recent_activity': recent_activity,
        }
        
        return render(request, 'crm/document/dashboard.html', context)
    
    def get_dashboard_stats(self, documents, user):
        """Get dashboard statistics"""
        today = timezone.now().date()
        week_start = today - timedelta(days=today.weekday())
        month_start = today.replace(day=1)
        
        stats = {
            'total_documents': documents.count(),
            'my_documents': documents.filter(owner=user).count(),
            'shared_with_me': documents.filter(shares__user=user).count(),
            'public_documents': documents.filter(access_level='PUBLIC').count(),
            'today_created': documents.filter(created_at__date=today).count(),
            'week_created': documents.filter(created_at__date__gte=week_start).count(),
            'month_created': documents.filter(created_at__date__gte=month_start).count(),
            'total_downloads': documents.aggregate(Sum('download_count'))['download_count__sum'] or 0,
            'total_views': documents.aggregate(Sum('view_count'))['view_count__sum'] or 0,
            'by_type': list(documents.values('document_type').annotate(
                count=Count('id')
            ).order_by('-count')),
            'by_access_level': list(documents.values('access_level').annotate(
                count=Count('id')
            ).order_by('-count')),
        }
        
        # Version tracking
        stats['total_versions'] = documents.filter(parent_document__isnull=False).count()
        stats['current_versions'] = documents.filter(is_current_version=True).count()
        
        return stats
    
    def get_category_stats(self, documents):
        """Get document statistics by category"""
        return list(documents.filter(
            category__isnull=False
        ).values(
            'category__name',
            'category__color',
            'category__icon'
        ).annotate(
            count=Count('id'),
            total_size=Sum('file_size')
        ).order_by('-count'))
    
    def get_storage_stats(self, documents):
        """Get storage usage statistics"""
        total_size = documents.aggregate(Sum('file_size'))['file_size__sum'] or 0
        
        # Convert bytes to appropriate units
        if total_size > 1024 * 1024 * 1024:  # GB
            size_display = f"{total_size / (1024 * 1024 * 1024):.2f} GB"
        elif total_size > 1024 * 1024:  # MB
            size_display = f"{total_size / (1024 * 1024):.2f} MB"
        else:  # KB
            size_display = f"{total_size / 1024:.2f} KB"
        
        # File type distribution
        type_distribution = list(documents.values('mime_type').annotate(
            count=Count('id'),
            total_size=Sum('file_size')
        ).order_by('-total_size')[:10])
        
        return {
            'total_size_bytes': total_size,
            'total_size_display': size_display,
            'type_distribution': type_distribution,
            'average_file_size': total_size / max(documents.count(), 1),
        }
    
    def get_recent_activity(self, documents):
        """Get recent document activity"""
        # Get recently accessed documents
        recent_access = documents.filter(
            last_accessed__isnull=False
        ).order_by('-last_accessed')[:10]
        
        activity = []
        for doc in recent_access:
            activity.append({
                'type': 'access',
                'document': doc,
                'user': doc.last_accessed_by,
                'timestamp': doc.last_accessed,
                'description': f'Accessed "{doc.title}"'
            })
        
        return sorted(activity, key=lambda x: x['timestamp'], reverse=True)[:20]


class DocumentListView(CRMBaseMixin, ListView):
    """Document list view with advanced filtering and search"""
    
    model = Document
    template_name = 'crm/document/list.html'
    context_object_name = 'documents'
    paginate_by = 25
    
    def get_queryset(self):
        queryset = Document.objects.filter(
            tenant=self.request.tenant,
            is_active=True
        ).select_related(
            'category', 'owner', 'content_type', 'parent_document'
        ).prefetch_related(
            'shares'
        ).annotate(
            shares_count=Count('shares', filter=Q(shares__is_active=True))
        )
        
        # User-based filtering
        user = self.request.user
        if not user.has_perm('crm.view_all_documents'):
            queryset = queryset.filter(
                Q(owner=user) |
                Q(access_level='PUBLIC') |
                Q(shares__user=user)
            ).distinct()
        
        # Apply filters
        document_filter = DocumentFilter(
            self.request.GET,
            queryset=queryset,
            tenant=self.request.tenant
        )
        
        # View type ordering
        view_type = self.request.GET.get('view', 'list')
        if view_type == 'grid':
            return document_filter.qs.order_by('-created_at')
        else:
            return document_filter.qs.order_by('-created_at')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Filter form
        context['filter'] = DocumentFilter(
            self.request.GET,
            tenant=self.request.tenant
        )
        
        # View type
        context['view_type'] = self.request.GET.get('view', 'list')
        
        # Categories for sidebar
        context['categories'] = DocumentCategory.objects.filter(
            tenant=self.request.tenant,
            is_active=True
        ).annotate(
            documents_count=Count('documents', filter=Q(documents__is_active=True))
        ).order_by('name')
        
        # Document statistics
        queryset = self.get_queryset()
        context['stats'] = self.get_document_list_stats(queryset)
        
        # Quick filters
        context['quick_filters'] = self.get_quick_filters()
        
        return context
    
    def get_document_list_stats(self, queryset):
        """Get statistics for the document list"""
        return {
            'total_count': queryset.count(),
            'my_documents': queryset.filter(owner=self.request.user).count(),
            'shared_documents': queryset.filter(shares__user=self.request.user).count(),
            'recent_documents': queryset.filter(
                created_at__date__gte=timezone.now().date() - timedelta(days=7)
            ).count(),
            'total_size': queryset.aggregate(Sum('file_size'))['file_size__sum'] or 0,
            'by_type': list(queryset.values('document_type').annotate(
                count=Count('id')
            ).order_by('-count')[:5]),
        }
    
    def get_quick_filters(self):
        """Get quick filter options"""
        return [
            {'name': 'My Documents', 'filter': 'owner=me'},
            {'name': 'Shared with Me', 'filter': 'shared_with_me=true'},
            {'name': 'Recent', 'filter': 'date_range=week'},
            {'name': 'Images', 'filter': 'type=IMAGE'},
            {'name': 'PDFs', 'filter': 'type=PDF'},
            {'name': 'Contracts', 'filter': 'type=CONTRACT'},
            {'name': 'Public', 'filter': 'access_level=PUBLIC'},
        ]


class DocumentDetailView(CRMBaseMixin, DetailView):
    """Comprehensive document detail view"""
    
    model = Document
    template_name = 'crm/document/detail.html'
    context_object_name = 'document'
    
    def get_queryset(self):
        return Document.objects.filter(
            tenant=self.request.tenant
        ).select_related(
            'category', 'owner', 'content_type', 'parent_document',
            'approved_by', 'last_accessed_by'
        ).prefetch_related(
            'shares__user',
            'shares__team',
            'versions'
        )
    
    def get(self, request, *args, **kwargs):
        response = super().get(request, *args, **kwargs)
        
        # Track document access
        document = self.get_object()
        document.track_access(request.user)
        
        return response
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        document = self.get_object()
        
        # Document versions
        if document.parent_document:
            # This is a version, get all versions of the parent
            context['all_versions'] = document.parent_document.versions.filter(
                is_active=True
            ).order_by('-created_at')
        else:
            # This is the parent, get its versions
            context['all_versions'] = document.versions.filter(
                is_active=True
            ).order_by('-created_at')
        
        # Document shares
        context['shares'] = document.shares.filter(
            is_active=True
        ).select_related('user', 'team')
        
        # Related documents (same category or related to same entity)
        context['related_documents'] = self.get_related_documents(document)
        
        # File information
        context['file_info'] = self.get_file_info(document)
        
        # Access permissions
        context['can_edit'] = self.can_user_edit(document, self.request.user)
        context['can_share'] = self.can_user_share(document, self.request.user)
        context['can_download'] = self.can_user_download(document, self.request.user)
        
        # Activity log
        context['activity_log'] = self.get_activity_log(document)
        
        # Preview availability
        context['can_preview'] = self.can_preview_document(document)
        
        return context
    
    def get_related_documents(self, document):
        """Get related documents"""
        related = Document.objects.filter(
            tenant=self.request.tenant,
            is_active=True
        ).exclude(id=document.id)
        
        # Same category
        if document.category:
            related = related.filter(category=document.category)
        
        # Same related entity
        if document.content_type and document.object_id:
            related = related.filter(
                content_type=document.content_type,
                object_id=document.object_id
            )
        
        return related.select_related('category', 'owner').order_by('-created_at')[:5]
    
    def get_file_info(self, document):
        """Get detailed file information"""
        file_info = {
            'size_display': self.format_file_size(document.file_size),
            'is_image': document.mime_type.startswith('image/') if document.mime_type else False,
            'is_pdf': document.mime_type == 'application/pdf',
            'is_office': self.is_office_document(document.mime_type),
            'extension': os.path.splitext(document.file_name)[1].lower(),
        }
        
        # Check if file exists
        if document.file_path and default_storage.exists(document.file_path):
            file_info['exists'] = True
        else:
            file_info['exists'] = False
        
        return file_info
    
    def format_file_size(self, size_bytes):
        """Format file size for display"""
        if size_bytes >= 1024 * 1024 * 1024:
            return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"
        elif size_bytes >= 1024 * 1024:
            return f"{size_bytes / (1024 * 1024):.2f} MB"
        elif size_bytes >= 1024:
            return f"{size_bytes / 1024:.2f} KB"
        else:
            return f"{size_bytes} bytes"
    
    def is_office_document(self, mime_type):
        """Check if document is an Office document"""
        office_types = [
            'application/vnd.ms-excel',
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            'application/vnd.ms-powerpoint',
            'application/vnd.openxmlformats-officedocument.presentationml.presentation',
            'application/msword',
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        ]
        return mime_type in office_types
    
    def can_user_edit(self, document, user):
        """Check if user can edit the document"""
        if user == document.owner or user.has_perm('crm.change_document'):
            return True
        
        # Check shared permissions
        share = document.shares.filter(user=user, permission_type__in=['EDIT', 'ADMIN']).first()
        return share is not None
    
    def can_user_share(self, document, user):
        """Check if user can share the document"""
        if user == document.owner or user.has_perm('crm.change_document'):
            return True
        
        share = document.shares.filter(user=user, permission_type='ADMIN').first()
        return share is not None
    
    def can_user_download(self, document, user):
        """Check if user can download the document"""
        if document.access_level == 'PUBLIC':
            return True
        
        if user == document.owner or user.has_perm('crm.view_document'):
            return True
        
        share = document.shares.filter(user=user).first()
        return share is not None
    
    def get_activity_log(self, document):
        """Get document activity log"""
        activity = [
            {
                'timestamp': document.created_at,
                'action': 'created',
                'user': document.created_by,
                'description': f'Document "{document.title}" was created',
            }
        ]
        
        if document.last_accessed:
            activity.append({
                'timestamp': document.last_accessed,
                'action': 'accessed',
                'user': document.last_accessed_by,
                'description': f'Document was accessed',
            })
        
        # Add share activities
        for share in document.shares.filter(is_active=True)[:5]:
            activity.append({
                'timestamp': share.created_at,
                'action': 'shared',
                'user': share.created_by,
                'description': f'Shared with {share.user.get_full_name() if share.user else "external user"}',
            })
        
        return sorted(activity, key=lambda x: x['timestamp'], reverse=True)
    
    def can_preview_document(self, document):
        """Check if document can be previewed"""
        if not document.mime_type:
            return False
        
        previewable_types = [
            'image/jpeg', 'image/png', 'image/gif', 'image/webp',
            'application/pdf',
            'text/plain', 'text/html', 'text/csv',
        ]
        
        return document.mime_type in previewable_types


class DocumentUploadView(CRMBaseMixin, PermissionRequiredMixin, View):
    """Handle document uploads"""
    
    permission_required = 'crm.add_document'
    
    def get(self, request):
        # Get upload form
        categories = DocumentCategory.objects.filter(
            tenant=request.tenant,
            is_active=True
        ).order_by('name')
        
        # Pre-populate related entity if specified
        content_type_id = request.GET.get('content_type_id')
        object_id = request.GET.get('object_id')
        related_object = None
        
        if content_type_id and object_id:
            try:
                content_type = ContentType.objects.get(id=content_type_id)
                related_object = content_type.get_object_for_this_type(id=object_id)
            except (ContentType.DoesNotExist, AttributeError):
                pass
        
        context = {
            'categories': categories,
            'related_object': related_object,
            'content_type_id': content_type_id,
            'object_id': object_id,
        }
        
        return render(request, 'crm/document/upload.html', context)
    
    def post(self, request):
        try:
            with transaction.atomic():
                uploaded_files = request.FILES.getlist('files')
                
                if not uploaded_files:
                    return JsonResponse({
                        'success': False,
                        'message': 'No files uploaded'
                    })
                
                uploaded_documents = []
                
                for uploaded_file in uploaded_files:
                    # Validate file
                    validation_result = self.validate_file(uploaded_file)
                    if not validation_result['valid']:
                        continue
                    
                    # Save file
                    file_path = self.save_uploaded_file(uploaded_file)
                    
                    # Create document record
                    document = Document.objects.create(
                        tenant=request.tenant,
                        title=request.POST.get('title') or os.path.splitext(uploaded_file.name)[0],
                        description=request.POST.get('description', ''),
                        document_type=request.POST.get('document_type', 'OTHER'),
                        file_name=uploaded_file.name,
                        file_path=file_path,
                        file_size=uploaded_file.size,
                        mime_type=uploaded_file.content_type or mimetypes.guess_type(uploaded_file.name)[0],
                        category_id=request.POST.get('category_id') or None,
                        access_level=request.POST.get('access_level', 'PRIVATE'),
                        owner=request.user,
                        created_by=request.user,
                    )
                    
                    # Set related object if specified
                    content_type_id = request.POST.get('content_type_id')
                    object_id = request.POST.get('object_id')
                    
                    if content_type_id and object_id:
                        try:
                            content_type = ContentType.objects.get(id=content_type_id)
                            document.content_type = content_type
                            document.object_id = object_id
                            document.save()
                        except ContentType.DoesNotExist:
                            pass
                    
                    # Generate file hash
                    self.generate_file_hash(document)
                    
                    uploaded_documents.append(document)
                
                return JsonResponse({
                    'success': True,
                    'message': f'Successfully uploaded {len(uploaded_documents)} documents',
                    'documents': [
                        {
                            'id': doc.id,
                            'title': doc.title,
                            'file_name': doc.file_name,
                            'size': doc.file_size,
                        }
                        for doc in uploaded_documents
                    ]
                })
        
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': str(e)
            })
    
    def validate_file(self, uploaded_file):
        """Validate uploaded file"""
        # Check file size (default 50MB limit)
        max_size = getattr(settings, 'MAX_UPLOAD_SIZE', 50 * 1024 * 1024)
        if uploaded_file.size > max_size:
            return {
                'valid': False,
                'message': f'File size exceeds {max_size / (1024 * 1024):.0f}MB limit'
            }
        
        # Check file type
        allowed_types = getattr(settings, 'ALLOWED_UPLOAD_TYPES', [
            'image/jpeg', 'image/png', 'image/gif', 'image/webp',
            'application/pdf', 'text/plain', 'text/csv',
            'application/msword', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            'application/vnd.ms-excel', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        ])
        
        content_type = uploaded_file.content_type or mimetypes.guess_type(uploaded_file.name)[0]
        if content_type and content_type not in allowed_types:
            return {
                'valid': False,
                'message': f'File type {content_type} not allowed'
            }
        
        return {'valid': True}
    
    def save_uploaded_file(self, uploaded_file):
        """Save uploaded file to storage"""
        # Generate unique filename
        timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{timestamp}_{uploaded_file.name}"
        
        # Create directory path based on date
        date_path = timezone.now().strftime('%Y/%m/%d')
        full_path = f"documents/{date_path}/{filename}"
        
        # Save file
        saved_path = default_storage.save(full_path, uploaded_file)
        return saved_path
    
    def generate_file_hash(self, document):
        """Generate SHA-256 hash for the file"""
        import hashlib
        
        try:
            if default_storage.exists(document.file_path):
                with default_storage.open(document.file_path, 'rb') as f:
                    file_hash = hashlib.sha256()
                    for chunk in iter(lambda: f.read(4096), b""):
                        file_hash.update(chunk)
                    
                    document.file_hash = file_hash.hexdigest()
                    document.save(update_fields=['file_hash'])
        except Exception:
            pass  # Fail silently


class DocumentDownloadView(CRMBaseMixin, PermissionRequiredMixin, View):
    """Handle document downloads"""
    
    permission_required = 'crm.view_document'
    
    def get(self, request, pk):
        document = get_object_or_404(
            Document,
            pk=pk,
            tenant=request.tenant,
            is_active=True
        )
        
        # Check download permission
        if not self.can_user_download(document, request.user):
            raise Http404("Document not found")
        
        # Check if file exists
        if not document.file_path or not default_storage.exists(document.file_path):
            messages.error(request, 'File not found on storage')
            return redirect('crm:document-detail', pk=pk)
        
        try:
            # Track download
            document.track_download(request.user)
            
            # Get file
            file_obj = default_storage.open(document.file_path, 'rb')
            response = FileResponse(
                file_obj,
                as_attachment=True,
                filename=document.file_name
            )
            
            # Set content type
            if document.mime_type:
                response['Content-Type'] = document.mime_type
            
            return response
        
        except Exception as e:
            messages.error(request, f'Error downloading file: {str(e)}')
            return redirect('crm:document-detail', pk=pk)
    
    def can_user_download(self, document, user):
        """Check if user can download the document"""
        if document.access_level == 'PUBLIC':
            return True
        
        if user == document.owner or user.has_perm('crm.view_all_documents'):
            return True
        
        share = document.shares.filter(user=user, is_active=True).first()
        return share is not None


class DocumentShareView(CRMBaseMixin, PermissionRequiredMixin, View):
    """Manage document sharing"""
    
    permission_required = 'crm.change_document'
    
    def get(self, request, pk):
        document = get_object_or_404(
            Document,
            pk=pk,
            tenant=request.tenant
        )
        
        # Check share permission
        if not self.can_user_share(document, request.user):
            messages.error(request, 'You do not have permission to share this document')
            return redirect('crm:document-detail', pk=pk)
        
        # Get existing shares
        shares = document.shares.filter(is_active=True).select_related('user', 'team')
        
        # Get available users and teams
        users = User.objects.filter(tenant=request.tenant, is_active=True)
        teams = Team.objects.filter(tenant=request.tenant, is_active=True)
        
        context = {
            'document': document,
            'shares': shares,
            'users': users,
            'teams': teams,
        }
        
        return render(request, 'crm/document/share.html', context)
    
    def post(self, request, pk):
        document = get_object_or_404(
            Document,
            pk=pk,
            tenant=request.tenant
        )
        
        if not self.can_user_share(document, request.user):
            return JsonResponse({
                'success': False,
                'message': 'Permission denied'
            })
        
        action = request.POST.get('action')
        
        try:
            if action == 'share_with_user':
                return self.share_with_user(document, request)
            elif action == 'share_with_team':
                return self.share_with_team(document, request)
            elif action == 'create_public_link':
                return self.create_public_link(document, request)
            elif action == 'share_external':
                return self.share_external(document, request)
            elif action == 'remove_share':
                return self.remove_share(document, request)
            else:
                return JsonResponse({
                    'success': False,
                    'message': 'Invalid action'
                })
        
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': str(e)
            })
    
    def share_with_user(self, document, request):
        """Share document with specific user"""
        user_id = request.POST.get('user_id')
        permission_type = request.POST.get('permission_type', 'VIEW')
        
        try:
            user = User.objects.get(id=user_id, tenant=request.tenant)
        except User.DoesNotExist:
            return JsonResponse({
                'success': False,
                'message': 'User not found'
            })
        
        # Check if already shared
        existing_share = document.shares.filter(user=user).first()
        if existing_share:
            existing_share.permission_type = permission_type
            existing_share.is_active = True
            existing_share.save()
            message = f'Updated sharing permissions for {user.get_full_name()}'
        else:
            DocumentShare.objects.create(
                tenant=request.tenant,
                document=document,
                share_type='USER',
                user=user,
                permission_type=permission_type,
                created_by=request.user
            )
            message = f'Shared document with {user.get_full_name()}'
        
        # Send notification
        try:
            notification_service = NotificationService(request.tenant)
            notification_service.send_document_share_notification(
                document, user, request.user
            )
        except Exception:
            pass  # Fail silently
        
        return JsonResponse({
            'success': True,
            'message': message
        })
    
    def share_with_team(self, document, request):
        """Share document with team"""
        team_id = request.POST.get('team_id')
        permission_type = request.POST.get('permission_type', 'VIEW')
        
        try:
            team = Team.objects.get(id=team_id, tenant=request.tenant)
        except Team.DoesNotExist:
            return JsonResponse({
                'success': False,
                'message': 'Team not found'
            })
        
        # Check if already shared
        existing_share = document.shares.filter(team=team).first()
        if existing_share:
            existing_share.permission_type = permission_type
            existing_share.is_active = True
            existing_share.save()
            message = f'Updated sharing permissions for {team.name}'
        else:
            DocumentShare.objects.create(
                tenant=request.tenant,
                document=document,
                share_type='TEAM',
                team=team,
                permission_type=permission_type,
                created_by=request.user
            )
            message = f'Shared document with team {team.name}'
        
        return JsonResponse({
            'success': True,
            'message': message
        })
    
    def create_public_link(self, document, request):
        """Create public sharing link"""
        expires_hours = int(request.POST.get('expires_hours', 24))
        password_required = request.POST.get('password_required') == 'true'
        share_password = request.POST.get('share_password', '')
        
        expires_at = timezone.now() + timedelta(hours=expires_hours)
        
        share = DocumentShare.objects.create(
            tenant=request.tenant,
            document=document,
            share_type='PUBLIC_LINK',
            permission_type='DOWNLOAD',
            expires_at=expires_at,
            password_required=password_required,
            share_password=share_password if password_required else '',
            created_by=request.user
        )
        
        # Generate share URL
        share_url = request.build_absolute_uri(
            f'/documents/public/{share.public_token}/'
        )
        
        return JsonResponse({
            'success': True,
            'message': 'Public link created',
            'share_url': share_url,
            'expires_at': expires_at.isoformat()
        })
    
    def share_external(self, document, request):
        """Share document with external email"""
        external_email = request.POST.get('external_email')
        permission_type = request.POST.get('permission_type', 'VIEW')
        message = request.POST.get('message', '')
        
        # Create share record
        share = DocumentShare.objects.create(
            tenant=request.tenant,
            document=document,
            share_type='EXTERNAL_EMAIL',
            external_email=external_email,
            permission_type=permission_type,
            expires_at=timezone.now() + timedelta(days=30),  # Default 30 days
            created_by=request.user
        )
        
        # Send email notification
        try:
            notification_service = NotificationService(request.tenant)
            notification_service.send_external_document_share_notification(
                document, external_email, request.user, message
            )
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': f'Failed to send email: {str(e)}'
            })
        
        return JsonResponse({
            'success': True,
            'message': f'Document shared with {external_email}'
        })
    
    def remove_share(self, document, request):
        """Remove document share"""
        share_id = request.POST.get('share_id')
        
        try:
            share = document.shares.get(id=share_id)
            share.is_active = False
            share.save()
            
            return JsonResponse({
                'success': True,
                'message': 'Share removed'
            })
        
        except DocumentShare.DoesNotExist:
            return JsonResponse({
                'success': False,
                'message': 'Share not found'
            })
    
    def can_user_share(self, document, user):
        """Check if user can share the document"""
        if user == document.owner or user.has_perm('crm.change_document'):
            return True
        
        share = document.shares.filter(user=user, permission_type='ADMIN').first()
        return share is not None


class DocumentVersionView(CRMBaseMixin, PermissionRequiredMixin, View):
    """Manage document versions"""
    
    permission_required = 'crm.change_document'
    
    def post(self, request, pk):
        document = get_object_or_404(
            Document,
            pk=pk,
            tenant=request.tenant
        )
        
        # Check edit permission
        if not self.can_user_edit(document, request.user):
            return JsonResponse({
                'success': False,
                'message': 'Permission denied'
            })
        
        action = request.POST.get('action')
        
        try:
            if action == 'upload_version':
                return self.upload_new_version(document, request)
            elif action == 'set_current':
                return self.set_current_version(document, request)
            elif action == 'restore_version':
                return self.restore_version(document, request)
            else:
                return JsonResponse({
                    'success': False,
                    'message': 'Invalid action'
                })
        
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': str(e)
            })
    
    def upload_new_version(self, document, request):
        """Upload new version of document"""
        uploaded_file = request.FILES.get('version_file')
        
        if not uploaded_file:
            return JsonResponse({
                'success': False,
                'message': 'No file uploaded'
            })
        
        # Save new file
        file_path = self.save_uploaded_file(uploaded_file)
        
        # Create new version
        new_version = document.create_new_version(
            file_path=file_path,
            file_name=uploaded_file.name,
            updated_by=request.user
        )
        
        return JsonResponse({
            'success': True,
            'message': f'New version {new_version.version} created',
            'version_id': new_version.id,
            'version': new_version.version
        })
    
    def save_uploaded_file(self, uploaded_file):
        """Save uploaded file to storage"""
        timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{timestamp}_{uploaded_file.name}"
        date_path = timezone.now().strftime('%Y/%m/%d')
        full_path = f"documents/{date_path}/{filename}"
        saved_path = default_storage.save(full_path, uploaded_file)
        return saved_path
    
    def can_user_edit(self, document, user):
        """Check if user can edit the document"""
        if user == document.owner or user.has_perm('crm.change_document'):
            return True
        
        share = document.shares.filter(user=user, permission_type__in=['EDIT', 'ADMIN']).first()
        return share is not None


class DocumentCategoryView(CRMBaseMixin, PermissionRequiredMixin, View):
    """Manage document categories"""
    
    permission_required = 'crm.manage_document_categories'
    
    def get(self, request):
        categories = DocumentCategory.objects.filter(
            tenant=request.tenant,
            is_active=True
        ).annotate(
            documents_count=Count('documents', filter=Q(documents__is_active=True)),
            total_size=Sum('documents__file_size', filter=Q(documents__is_active=True))
        ).order_by('name')
        
        context = {
            'categories': categories,
        }
        
        return render(request, 'crm/document/categories.html', context)
    
    def post(self, request):
        action = request.POST.get('action')
        
        try:
            if action == 'create_category':
                return self.create_category(request)
            elif action == 'update_category':
                return self.update_category(request)
            elif action == 'delete_category':
                return self.delete_category(request)
            else:
                return JsonResponse({
                    'success': False,
                    'message': 'Invalid action'
                })
        
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': str(e)
            })
    
    def create_category(self, request):
        """Create new document category"""
        category = DocumentCategory.objects.create(
            tenant=request.tenant,
            name=request.POST.get('name'),
            description=request.POST.get('description', ''),
            color=request.POST.get('color', '#007bff'),
            icon=request.POST.get('icon', ''),
            parent_id=request.POST.get('parent_id') or None,
            max_file_size_mb=int(request.POST.get('max_file_size_mb', 10)),
            allowed_file_types=json.loads(request.POST.get('allowed_file_types', '[]')),
            created_by=request.user
        )
        
        return JsonResponse({
            'success': True,
            'message': f'Category "{category.name}" created',
            'category_id': category.id
        })


# ============================================================================
# API ViewSets
# ============================================================================

class DocumentViewSet(CRMBaseViewSet):
    """Document API ViewSet with comprehensive functionality"""
    
    queryset = Document.objects.all()
    permission_classes = [DocumentPermission]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = DocumentFilter
    search_fields = ['title', 'description', 'file_name', 'tags']
    ordering_fields = ['created_at', 'title', 'file_size', 'download_count']
    ordering = ['-created_at']
    
    def get_serializer_class(self):
        if self.action == 'retrieve':
            return DocumentDetailSerializer
        return DocumentSerializer
    
    def get_queryset(self):
        queryset = super().get_queryset().select_related(
            'category', 'owner', 'content_type', 'parent_document'
        ).prefetch_related(
            'shares'
        ).annotate(
            shares_count=Count('shares', filter=Q(shares__is_active=True))
        )
        
        # User-based filtering
        user = self.request.user
        if not user.has_perm('crm.view_all_documents'):
            queryset = queryset.filter(
                Q(owner=user) |
                Q(access_level='PUBLIC') |
                Q(shares__user=user)
            ).distinct()
        
        return queryset
    
    @action(detail=True, methods=['get'])
    def download(self, request, pk=None):
        """Download document file"""
        document = self.get_object()
        
        # Check download permission
        if not self.can_user_download(document, request.user):
            return Response(
                {'error': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Check if file exists
        if not document.file_path or not default_storage.exists(document.file_path):
            return Response(
                {'error': 'File not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Track download
        document.track_download(request.user)
        
        # Return file URL or stream
        if hasattr(default_storage, 'url'):
            file_url = default_storage.url(document.file_path)
            return Response({'download_url': file_url})
        else:
            # Stream file content
            file_obj = default_storage.open(document.file_path, 'rb')
            response = FileResponse(
                file_obj,
                as_attachment=True,
                filename=document.file_name
            )
            
            if document.mime_type:
                response['Content-Type'] = document.mime_type
            
            return response
    
    @action(detail=True, methods=['post'])
    def share(self, request, pk=None):
        """Share document with users"""
        document = self.get_object()
        
        if not self.can_user_share(document, request.user):
            return Response(
                {'error': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        serializer = DocumentShareSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(
                tenant=request.tenant,
                document=document,
                created_by=request.user
            )
            
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['get'])
    def versions(self, request, pk=None):
        """Get document versions"""
        document = self.get_object()
        
        if document.parent_document:
            # This is a version, get all versions of the parent
            versions = document.parent_document.versions.filter(is_active=True)
        else:
            # This is the parent, get its versions
            versions = document.versions.filter(is_active=True)
        
        versions = versions.order_by('-created_at')
        serializer = DocumentSerializer(versions, many=True, context={'request': request})
        return Response(serializer.data)
    
    @action(detail=False, methods=['post'])
    def bulk_download(self, request):
        """Bulk download documents as zip"""
        document_ids = request.data.get('document_ids', [])
        
        if not document_ids:
            return Response(
                {'error': 'No documents selected'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        documents = self.get_queryset().filter(id__in=document_ids)
        
        # Create zip file
        zip_buffer = BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            for document in documents:
                if document.file_path and default_storage.exists(document.file_path):
                    try:
                        with default_storage.open(document.file_path, 'rb') as file_obj:
                            zip_file.writestr(document.file_name, file_obj.read())
                    except Exception:
                        continue  # Skip files that can't be read
        
        zip_buffer.seek(0)
        
        response = HttpResponse(
            zip_buffer.getvalue(),
            content_type='application/zip'
        )
        response['Content-Disposition'] = 'attachment; filename="documents.zip"'
        
        return response
    
    def can_user_download(self, document, user):
        """Check if user can download the document"""
        if document.access_level == 'PUBLIC':
            return True
        
        if user == document.owner or user.has_perm('crm.view_all_documents'):
            return True
        
        share = document.shares.filter(user=user, is_active=True).first()
        return share is not None
    
    def can_user_share(self, document, user):
        """Check if user can share the document"""
        if user == document.owner or user.has_perm('crm.change_document'):
            return True
        
        share = document.shares.filter(user=user, permission_type='ADMIN').first()
        return share is not None


class DocumentCategoryViewSet(CRMBaseViewSet):
    """Document Category API ViewSet"""
    
    queryset = DocumentCategory.objects.all()
    serializer_class = DocumentCategorySerializer
    permission_classes = [DocumentPermission]
    
    def get_queryset(self):
        return super().get_queryset().annotate(
            documents_count=Count('documents', filter=Q(documents__is_active=True)),
            total_size=Sum('documents__file_size', filter=Q(documents__is_active=True))
        )


class DocumentShareViewSet(CRMBaseViewSet):
    """Document Share API ViewSet"""
    
    queryset = DocumentShare.objects.all()
    serializer_class = DocumentShareSerializer
    permission_classes = [DocumentPermission]
    
    def get_queryset(self):
        return super().get_queryset().select_related(
            'document', 'user', 'team'
        )