# ============================================================================
# backend/apps/crm/services/document_service.py - Document Management Service
# ============================================================================

from typing import Dict, List, Any, Optional, BinaryIO
from django.db import transaction
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from django.utils import timezone
from django.contrib.contenttypes.models import ContentType
import os
import hashlib
import mimetypes
from pathlib import Path

from .base import BaseService, CacheableMixin, NotificationMixin, CRMServiceException
from ..models import Document, DocumentCategory, DocumentShare


class DocumentService(BaseService, CacheableMixin, NotificationMixin):
    """Comprehensive document management service with version control"""
    
    def __init__(self, tenant, user=None):
        super().__init__(tenant, user)
        self.allowed_file_types = self._get_allowed_file_types()
        self.max_file_size = self._get_max_file_size()
    
    @transaction.atomic
    def upload_document(self, file_: Dict, 
                       related_object=None) -> Document:
        """Upload document with validation and metadata extraction"""
        
        # Validate file
        validation_result = self._validate_file(file_data, document_info)
        if not validation_result['valid']:
            raise CRMServiceException(validation_result['error'])
        
        # Generate file path and save
        file_path = self._generate_file_path(document_info['file_name'])
        saved_path = default_storage.save(file_path, ContentFile(file_data.read()))
        
        # Calculate file hash
        file_data.seek(0)
        file_hash = self._calculate_file_hash(file_data)
        
        # Check for duplicates
        if document_info.get('check_duplicates', True):
            duplicate = self._check_duplicate_document(file_hash)
            if duplicate:
                default_storage.delete(saved_path)  # Clean up uploaded file
                raise CRMServiceException(f"Duplicate document found: {duplicate.title}")
        
        # Extract metadata
        metadata = self._extract_file_metadata(file_data, document_info['file_name'])
        
        # Create document record
        document_data = {
            'tenant': self.tenant,
            'title': document_info.get('title', document_info['file_name']),
            'description': document_info.get('description', ''),
            'document_type': self._detect_document_type(document_info['file_name']),
            'file_name': document_info['file_name'],
            'file_path': saved_path,
            'file_size': file_data.tell(),
            'mime_type': metadata['mime_type'],
            'file_hash': file_hash,
            'category': document_info.get('category'),
            'tags': document_info.get('tags', []),
            'access_level': document_info.get('access_level', 'PRIVATE'),
            'owner': self.user,
            'created_by': self.user,
        }
        
        # Link to related object if provided
        if related_object:
            document_data.update({
                'content_type': ContentType.objects.get_for_model(related_object),
                'object_id': str(related_object.pk),
            })
        
        document = Document.objects.create(**document_data)
        
        # Create audit trail
        self.create_audit_trail('CREATE', document)
        
        self.logger.info(f"Document uploaded: {document.title} ({document.file_size} bytes)")
        return document
    
    @transaction.atomic
    def create_document_version(self, document_id: 
                               version_info: Dict) -> Document:
        """Create new version of existing document"""
        
        parent_document = self.get_queryset(Document).get(id=document_id)
        
        if parent_document.owner != self.user and not self.check_permission('can_edit_all_documents'):
            raise PermissionDenied("Cannot create version for documents not owned by you")
        
        # Upload new version
        new_version = self.upload_document(file_data, {
            'file_name': version_info.get('file_name', parent_document.file_name),
            'title': parent_document.title,
            'description': version_info.get('description', parent_document.description),
            'category': parent_document.category,
            'tags': parent_document.tags,
            'access_level': parent_document.access_level,
        })
        
        # Set version information
        new_version.parent_document = parent_document.parent_document or parent_document
        new_version.version = self._increment_version(parent_document.version)
        new_version.is_current_version = True
        new_version.save()
        
        # Mark other versions as not current
        Document.objects.filter(
            tenant=self.tenant,
            parent_document=new_version.parent_document
        ).exclude(id=new_version.id).update(is_current_version=False)
        
        parent_document.is_current_version = False
        parent_document.save()
        
        return new_version
    
    def download_document(self, document_id: int, track_download: bool = True) -> Dict:
        """Download document with access control and tracking"""
        
        document = self.get_queryset(Document).get(id=document_id)
        
        # Check access permissions
        if not self._can_access_document(document, 'DOWNLOAD'):
            raise PermissionDenied("No permission to download this document")
        
        # Check if file exists
        if not default_storage.exists(document.file_path):
            raise CRMServiceException("Document file not found on storage")
        
        # Track download
        if track_download:
            document.track_download(self.user)
        
        # Get file URL (for cloud storage) or path (for local storage)
        file_url = default_storage.url(document.file_path)
        
        return {
            'file_url': file_url,
            'file_name': document.file_name,
            'file_size': document.file_size,
            'mime_type': document.mime_type,
            'download_count': document.download_count,
        }
    
    @transaction.atomic
    def share_document(self, document_id: int, share_config: Dict) -> DocumentShare:
        """Share document with users or create public link"""
        
        document = self.get_queryset(Document).get(id=document_id)
        
        if document.owner != self.user and not self.check_permission('can_share_documents'):
            raise PermissionDenied("Cannot share documents not owned by you")
        
        share_data = {
            'tenant': self.tenant,
            'document': document,
            'share_type': share_config.get('share_type', 'USER'),
            'permission_type': share_config.get('permission_type', 'VIEW'),
            'expires_at': share_config.get('expires_at'),
            'max_downloads': share_config.get('max_downloads'),
            'password_required': share_config.get('password_required', False),
            'share_password': share_config.get('share_password', ''),
            'notify_on_access': share_config.get('notify_on_access', False),
        }
        
        # Set recipient based on share type
        if share_config['share_type'] == 'USER':
            share_data['user'] = share_config['user']
        elif share_config['share_type'] == 'TEAM':
            share_data['team'] = share_config['team']
        elif share_config['share_type'] == 'EXTERNAL_EMAIL':
            share_data['external_email'] = share_config['external_email']
        
        document_share = DocumentShare.objects.create(**share_data)
        
        # Send notification to recipient
        if share_config.get('send_notification', True):
            self._send_share_notification(document_share)
        
        return document_share
    
    def search_documents(self, search_query: str, filters: Dict = None) -> Dict:
        """Search documents with full-text search and filters"""
        
        queryset = self.get_queryset(Document)
        
        # Apply search query
        if search_query:
            queryset = queryset.filter(
                models.Q(title__icontains=search_query) |
                models.Q(description__icontains=search_query) |
                models.Q(tags__contains=[search_query])
            )
        
        # Apply filters
        if filters:
            if filters.get('category'):
                queryset = queryset.filter(category=filters['category'])
            if filters.get('document_type'):
                queryset = queryset.filter(document_type=filters['document_type'])
            if filters.get('owner'):
                queryset = queryset.filter(owner=filters['owner'])
            if filters.get('date_from'):
                queryset = queryset.filter(created_at__gte=filters['date_from'])
            if filters.get('date_to'):
                queryset = queryset.filter(created_at__lte=filters['date_to'])
            if filters.get('file_size_min'):
                queryset = queryset.filter(file_size__gte=filters['file_size_min'])
            if filters.get('file_size_max'):
                queryset = queryset.filter(file_size__lte=filters['file_size_max'])
        
        # Apply access control
        queryset = self._apply_access_control(queryset)
        
        # Get results with pagination
        total_count = queryset.count()
        documents = queryset.order_by('-created_at')
        
        return {
            'documents': documents,
            'total_count': total_count,
            'query': search_query,
            'filters': filters or {},
        }
    
    def organize_documents(self, organization_config: Dict) -> Dict:
        """Organize documents into categories and apply tags"""
        
        document_ids = organization_config.get('document_ids', [])
        action = organization_config.get('action')  # 'categorize', 'tag', 'move'
        
        documents = self.get_queryset(Document).filter(id__in=document_ids)
        updated_count = 0
        
        with transaction.atomic():
            for document in documents:
                if not self._can_access_document(document, 'EDIT'):
                    continue
                
                if action == 'categorize':
                    category_id = organization_config.get('category_id')
                    if category_id:
                        document.category_id = category_id
                        document.save()
                        updated_count += 1
                
                elif action == 'tag':
                    tags_to_add = organization_config.get('tags', [])
                    existing_tags = set(document.tags)
                    new_tags = existing_tags.union(set(tags_to_add))
                    document.tags = list(new_tags)
                    document.save()
                    updated_count += 1
                
                elif action == 'move':
                    new_access_level = organization_config.get('access_level')
                    if new_access_level:
                        document.access_level = new_access_level
                        document.save()
                        updated_count += 1
        
        return {
            'action': action,
            'total_documents': len(document_ids),
            'updated_count': updated_count,
        }
    
    def get_document_analytics(self, filters: Dict = None) -> Dict:
        """Get comprehensive document analytics"""
        
        queryset = self.get_queryset(Document)
        
        if filters:
            if filters.get('date_from'):
                queryset = queryset.filter(created_at__gte=filters['date_from'])
            if filters.get('date_to'):
                queryset = queryset.filter(created_at__lte=filters['date_to'])
        
        # Basic statistics
        total_documents = queryset.count()
        total_size = queryset.aggregate(total=models.Sum('file_size'))['total'] or 0
        average_size = queryset.aggregate(avg=models.Avg('file_size'))['avg'] or 0
        
        # Document type distribution
        type_distribution = queryset.values('document_type').annotate(
            count=models.Count('id'),
            total_size=models.Sum('file_size')
        ).order_by('-count')
        
        # Category distribution
        category_distribution = queryset.values('category__name').annotate(
            count=models.Count('id')
        ).order_by('-count')
        
        # Access level distribution
        access_distribution = queryset.values('access_level').annotate(
            count=models.Count('id')
        ).order_by('-count')
        
        # Most active users
        user_activity = queryset.values(
            'owner__first_name', 'owner__last_name'
        ).annotate(
            document_count=models.Count('id'),
            total_downloads=models.Sum('download_count')
        ).order_by('-document_count')[:10]
        
        # Storage usage by month
        monthly_storage = queryset.extra(
            select={'month': 'EXTRACT(month FROM created_at)'}
        ).values('month').annotate(
            count=models.Count('id'),
            size=models.Sum('file_size')
        ).order_by('month')
        
        # Most downloaded documents
        popular_documents = queryset.filter(
            download_count__gt=0
        ).order_by('-download_count')[:10].values(
            'title', 'download_count', 'view_count', 'file_size'
        )
        
        return {
            'summary': {
                'total_documents': total_documents,
                'total_size_bytes': total_size,
                'total_size_mb': round(total_size / (1024 * 1024), 2),
                'average_size_bytes': round(average_size, 2),
            },
            'distributions': {
                'by_type': list(type_distribution),
                'by_category': list(category_distribution),
                'by_access_level': list(access_distribution),
            },
            'user_activity': list(user_activity),
            'storage_trends': list(monthly_storage),
            'popular_documents': list(popular_documents),
        }
    
    def cleanup_orphaned_files(self) -> Dict:
        """Clean up orphaned files and expired shares"""
        
        self.require_permission('can_manage_documents')
        
        cleaned_files = 0
        cleaned_shares = 0
        errors = []
        
        # Clean up orphaned files
        all_documents = Document.objects.filter(tenant=self.tenant)
        
        for document in all_documents:
            if not default_storage.exists(document.file_path):
                try:
                    document.delete()
                    cleaned_files += 1
                except Exception as e:
                    errors.append(f"Failed to delete orphaned document {document.id}: {str(e)}")
        
        # Clean up expired shares
        expired_shares = DocumentShare.objects.filter(
            tenant=self.tenant,
            expires_at__lt=timezone.now()
        )
        
        cleaned_shares = expired_shares.count()
        expired_shares.delete()
        
        # Clean up files not referenced by any document
        # This would require more sophisticated file system scanning
        
        return {
            'cleaned_files': cleaned_files,
            'cleaned_shares': cleaned_shares,
            'errors': errors,
        }
    
    def _validate_file(self, file_data: BinaryIO, document_info: Dict) -> Dict:
        """Validate uploaded file"""
        
        file_name = document_info.get('file_name', '')
        file_size = len(file_data.read())
        file_data.seek(0)
        
        # Check file size
        if file_size > self.max_file_size:
            return {
                'valid': False,
                'error': f'File size ({file_size} bytes) exceeds maximum allowed ({self.max_file_size} bytes)'
            }
        
        # Check file type
        file_extension = Path(file_name).suffix.lower()
        if file_extension not in self.allowed_file_types:
            return {
                'valid': False,
                'error': f'File type {file_extension} is not allowed'
            }
        
        # Check for malicious content (basic)
        file_data.seek(0)
        file_header = file_data.read(1024)
        file_data.seek(0)
        
        # Basic malware signature detection (very simplified)
        malicious_signatures = [b'<script', b'javascript:', b'vbscript:']
        for signature in malicious_signatures:
            if signature in file_header.lower():
                return {
                    'valid': False,
                    'error': 'File contains potentially malicious content'
                }
        
        return {'valid': True}
    
    def _calculate_file_hash(self, file str:
        """Calculate SHA-256 hash of file"""
        
        hash_sha256 = hashlib.sha256()
        file_data.seek(0)
        
        for chunk in iter(lambda: file_data.read(4096), b""):
            hash_sha256.update(chunk)
        
        file_data.seek(0)
        return hash_sha256.hexdigest()
    
    def _check_duplicate_document(self, file_hash: str) -> Optional[Document]:
        """Check for duplicate document by file hash"""
        
        return Document.objects.filter(
            tenant=self.tenant,
            file_hash=file_hash,
            is_active=True
        ).first()
    
    def _extract_file_metadata file_name: str) -> Dict:
        """Extract metadata from file"""
        
        # Get MIME type
        mime_type, _ = mimetypes.guess_type(file_name)
        if not mime_type:
            mime_type = 'application/octet-stream'
        
        metadata = {
            'mime_type': mime_type,
            'file_name': file_name,
            'file_size': len(file_data.read()),
        }
        
        file_data.seek(0)
        return metadata
    
    def _generate_file_path(self, file_name: str) -> str:
        """Generate unique file path for storage"""
        
        # Create path with tenant ID and date structure
        date_path = timezone.now().strftime('%Y/%m/%d')
        unique_id = timezone.now().strftime('%H%M%S') + '_' + str(hash(file_name))[:8]
        
        file_extension = Path(file_name).suffix
        new_file_name = f"{unique_id}{file_extension}"
        
        return f"documents/{self.tenant.id}/{date_path}/{new_file_name}"
    
    def _detect_document_type(self, file_name: str) -> str:
        """Detect document type based on file extension"""
        
        file_extension = Path(file_name).suffix.lower()
        
        type_mapping = {
            '.pdf': 'PDF',
            '.doc': 'DOCUMENT',
            '.docx': 'DOCUMENT',
            '.xls': 'SPREADSHEET',
            '.xlsx': 'SPREADSHEET',
            '.ppt': 'PRESENTATION',
            '.pptx': 'PRESENTATION',
            '.jpg': 'IMAGE',
            '.jpeg': 'IMAGE',
            '.png': 'IMAGE',
            '.gif': 'IMAGE',
            '.mp4': 'VIDEO',
            '.avi': 'VIDEO',
            '.mov': 'VIDEO',
            '.mp3': 'AUDIO',
            '.wav': 'AUDIO',
            '.txt': 'TEXT',
            '.csv': 'SPREADSHEET',
        }
        
        return type_mapping.get(file_extension, 'OTHER')
    
    def _can_access_document(self, document: Document, permission: str) -> bool:
        """Check if user can access document with specific permission"""
        
        # Owner can do everything
        if document.owner == self.user:
            return True
        
        # Check global permissions
        if permission == 'VIEW' and self.check_permission('can_view_all_documents'):
            return True
        if permission == 'EDIT' and self.check_permission('can_edit_all_documents'):
            return True
        if permission == 'DOWNLOAD' and self.check_permission('can_download_all_documents'):
            return True
        
        # Check access level
        if document.access_level == 'PUBLIC':
            return True
        elif document.access_level == 'COMPANY':
            return True  # All tenant users can access
        elif document.access_level == 'TEAM':
            # Check if user is in the same team (would need team membership logic)
            return True
        
        # Check specific shares
        share = DocumentShare.objects.filter(
            document=document,
            user=self.user,
            expires_at__gt=timezone.now()
        ).first()
        
        if share and share.is_valid():
            permission_hierarchy = ['VIEW', 'DOWNLOAD', 'COMMENT', 'EDIT', 'ADMIN']
            user_permission_level = permission_hierarchy.index(share.permission_type)
            required_permission_level = permission_hierarchy.index(permission)
            return user_permission_level >= required_permission_level
        
        return False
    
    def _apply_access_control(self, queryset):
        """Apply access control to document queryset"""
        
        if self.check_permission('can_view_all_documents'):
            return queryset
        
        # Filter based on access levels and shares
        return queryset.filter(
            models.Q(owner=self.user) |
            models.Q(access_level='PUBLIC') |
            models.Q(access_level='COMPANY') |
            models.Q(shares__user=self.user, shares__expires_at__gt=timezone.now())
        ).distinct()
    
    def _increment_version(self, current_version: str) -> str:
        """Increment document version number"""
        
        try:
            parts = current_version.split('.')
            if len(parts) == 2:
                major, minor = int(parts[0]), int(parts[1])
                return f"{major}.{minor + 1}"
            else:
                return f"{int(current_version) + 1}.0"
        except (ValueError, AttributeError):
            return "2.0"
    
    def _send_share_notification(self, document_share: DocumentShare):
        """Send notification about document sharing"""
        
        if document_share.user:
            self.send_notification(
                [document_share.user],
                f"Document Shared: {document_share.document.title}",
                f"A document has been shared with you: {document_share.document.title}"
            )
        elif document_share.external_email:
            # Send email notification to external email
            pass
    
    def _get_allowed_file_types(self) -> set:
        """Get allowed file types from configuration"""
        
        default_types = {
            '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx',
            '.txt', '.csv', '.jpg', '.jpeg', '.png', '.gif', '.mp4',
            '.avi', '.mov', '.mp3', '.wav', '.zip', '.rar'
        }
        
        return getattr(self.tenant, 'allowed_file_types', default_types)
    
    def _get_max_file_size(self) -> int:
        """Get maximum file size from configuration"""
        
        default_size = 10 * 1024 * 1024  # 10 MB
        return getattr(self.tenant, 'max_file_size', default_size)