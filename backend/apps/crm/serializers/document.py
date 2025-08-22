# ============================================================================
# backend/apps/crm/serializers/document.py - Document Management Serializers
# ============================================================================

from rest_framework import serializers
from django.utils import timezone
from ..models import DocumentCategory, Document, DocumentShare
from .user import UserBasicSerializer


class DocumentCategorySerializer(serializers.ModelSerializer):
    """Document category serializer with hierarchy"""
    
    parent_name = serializers.CharField(source='parent.name', read_only=True)
    subcategories_count = serializers.SerializerMethodField()
    documents_count = serializers.SerializerMethodField()
    storage_summary = serializers.SerializerMethodField()
    
    class Meta:
        model = DocumentCategory
        fields = [
            'id', 'name', 'description', 'color', 'icon', 'parent',
            'parent_name', 'level', 'is_public', 'restricted_access',
            'allowed_users', 'max_file_size_mb', 'allowed_file_types',
            'require_approval', 'total_documents', 'total_size_bytes',
            'subcategories_count', 'documents_count', 'storage_summary',
            'is_active', 'sort_order',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'parent_name', 'level', 'total_documents', 'total_size_bytes',
            'subcategories_count', 'documents_count', 'storage_summary',
            'created_at', 'updated_at'
        ]
    
    def get_subcategories_count(self, obj):
        """Get count of subcategories"""
        return obj.subcategories.filter(is_active=True).count()
    
    def get_documents_count(self, obj):
        """Get count of documents in category"""
        return obj.documents.filter(is_active=True).count()
    
    def get_storage_summary(self, obj):
        """Get storage usage summary"""
        size_mb = obj.total_size_bytes / (1024 * 1024) if obj.total_size_bytes else 0
        return {
            'total_documents': obj.total_documents,
            'total_size_mb': round(size_mb, 2),
            'average_size_mb': round(size_mb / max(obj.total_documents, 1), 2),
            'storage_utilization': f"{round(size_mb, 1)} MB"
        }


class DocumentShareSerializer(serializers.ModelSerializer):
    """Document sharing serializer"""
    
    user_details = UserBasicSerializer(source='user', read_only=True)
    team_name = serializers.CharField(source='team.name', read_only=True)
    document_title = serializers.CharField(source='document.title', read_only=True)
    
    # Share status
    is_valid = serializers.SerializerMethodField()
    expires_in_days = serializers.SerializerMethodField()
    usage_summary = serializers.SerializerMethodField()
    
    class Meta:
        model = DocumentShare
        fields = [
            'id', 'document', 'document_title', 'share_type', 'permission_type',
            'user', 'user_details', 'team', 'team_name', 'external_email',
            'public_token', 'password_required', 'share_password',
            'expires_at', 'expires_in_days', 'max_downloads', 'download_count',
            'last_accessed', 'access_count', 'is_valid', 'usage_summary',
            'notify_on_access', 'notify_on_download',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'document_title', 'user_details', 'team_name', 'public_token',
            'download_count', 'last_accessed', 'access_count', 'is_valid',
            'expires_in_days', 'usage_summary', 'created_at', 'updated_at'
        ]
    
    def get_is_valid(self, obj):
        """Check if share is still valid"""
        return obj.is_valid()
    
    def get_expires_in_days(self, obj):
        """Get days until expiration"""
        if obj.expires_at:
            remaining = obj.expires_at - timezone.now()
            return max(0, remaining.days)
        return None
    
    def get_usage_summary(self, obj):
        """Get share usage summary"""
        return {
            'total_accesses': obj.access_count,
            'total_downloads': obj.download_count,
            'downloads_remaining': (obj.max_downloads - obj.download_count) if obj.max_downloads else None,
            'last_activity': obj.last_accessed,
            'is_active': obj.access_count > 0 or obj.download_count > 0
        }


class DocumentSerializer(serializers.ModelSerializer):
    """Comprehensive document serializer"""
    
    category_details = DocumentCategorySerializer(source='category', read_only=True)
    owner_details = UserBasicSerializer(source='owner', read_only=True)
    approved_by_details = UserBasicSerializer(source='approved_by', read_only=True)
    last_accessed_by_details = UserBasicSerializer(source='last_accessed_by', read_only=True)
    
    # Document sharing
    shares = DocumentShareSerializer(many=True, read_only=True)
    shares_count = serializers.SerializerMethodField()
    
    # File information
    file_size_formatted = serializers.SerializerMethodField()
    file_age = serializers.SerializerMethodField()
    
    # Version information
    versions_count = serializers.SerializerMethodField()
    has_newer_version = serializers.SerializerMethodField()
    
    # Security and access
    access_summary = serializers.SerializerMethodField()
    security_status = serializers.SerializerMethodField()
    
    # Generic relation
    related_to_type = serializers.CharField(source='content_type.model', read_only=True)
    related_to_name = serializers.SerializerMethodField()
    
    class Meta:
        model = Document
        fields = [
            'id', 'title', 'description', 'document_type', 'file_name',
            'file_path', 'file_size', 'file_size_formatted', 'mime_type',
            'file_hash', 'file_age',
            # Versioning
            'version', 'is_current_version', 'parent_document', 'versions_count',
            'has_newer_version',
            # Organization
            'category', 'category_details', 'tags',
            # Relations
            'content_type', 'object_id', 'related_to_type', 'related_to_name',
            # Access control
            'access_level', 'owner', 'owner_details',
            # Approval
            'requires_approval', 'is_approved', 'approved_by',
            'approved_by_details', 'approved_date',
            # Tracking
            'download_count', 'view_count', 'last_accessed',
            'last_accessed_by', 'last_accessed_by_details',
            # Security
            'is_encrypted', 'password_protected', 'security_status',
            # External integration
            'external_url', 'cloud_storage_id', 'cloud_storage_provider',
            # Expiration
            'expires_at', 'auto_delete_on_expiry',
            # Sharing
            'shares', 'shares_count', 'access_summary',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'file_size', 'file_size_formatted', 'mime_type', 'file_hash',
            'file_age', 'category_details', 'owner_details', 'approved_by_details',
            'last_accessed_by_details', 'versions_count', 'has_newer_version',
            'download_count', 'view_count', 'last_accessed', 'last_accessed_by',
            'shares', 'shares_count', 'access_summary', 'security_status',
            'related_to_type', 'related_to_name', 'created_at', 'updated_at'
        ]
    
    def get_shares_count(self, obj):
        """Get count of active shares"""
        return obj.shares.count()
    
    def get_file_size_formatted(self, obj):
        """Get human-readable file size"""
        size = obj.file_size
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} TB"
    
    def get_file_age(self, obj):
        """Get file age in days"""
        return (timezone.now() - obj.created_at).days
    
    def get_versions_count(self, obj):
        """Get count of versions"""
        if obj.parent_document:
            return obj.parent_document.versions.count()
        return obj.versions.count()
    
    def get_has_newer_version(self, obj):
        """Check if there's a newer version"""
        if obj.parent_document:
            return obj.parent_document.versions.filter(
                created_at__gt=obj.created_at,
                is_current_version=True
            ).exists()
        return False
    
    def get_access_summary(self, obj):
        """Get access summary"""
        return {
            'total_views': obj.view_count,
            'total_downloads': obj.download_count,
            'last_activity': obj.last_accessed,
            'is_shared': obj.shares.exists(),
            'access_level': obj.access_level,
            'recent_activity': obj.last_accessed and (timezone.now() - obj.last_accessed).days < 7
        }
    
    def get_security_status(self, obj):
        """Get security status"""
        status = 'Low'
        if obj.is_encrypted:
            status = 'High'
        elif obj.password_protected:
            status = 'Medium'
        elif obj.access_level == 'PRIVATE':
            status = 'Medium'
        
        return {
            'level': status,
            'encrypted': obj.is_encrypted,
            'password_protected': obj.password_protected,
            'access_restricted': obj.access_level in ['PRIVATE', 'TEAM']
        }
    
    def get_related_to_name(self, obj):
        """Get name of related object"""
        if obj.related_to:
            if hasattr(obj.related_to, 'name'):
                return obj.related_to.name
            elif hasattr(obj.related_to, 'full_name'):
                return obj.related_to.full_name
            return str(obj.related_to)
        return None


class DocumentDetailSerializer(DocumentSerializer):
    """Detailed document serializer with version history"""
    
    version_history = serializers.SerializerMethodField()
    sharing_history = serializers.SerializerMethodField()
    access_log = serializers.SerializerMethodField()
    
    class Meta(DocumentSerializer.Meta):
        fields = DocumentSerializer.Meta.fields + [
            'version_history', 'sharing_history', 'access_log'
        ]
    
    def get_version_history(self, obj):
        """Get version history"""
        if obj.parent_document:
            versions = obj.parent_document.versions.all()
        else:
            versions = obj.versions.all()
        
        return [
            {
                'id': version.id,
                'version': version.version,
                'created_at': version.created_at,
                'created_by': version.created_by.get_full_name() if version.created_by else None,
                'file_size': version.file_size,
                'is_current': version.is_current_version
            }
            for version in versions.order_by('-created_at')
        ]
    
    def get_sharing_history(self, obj):
        """Get sharing history"""
        return [
            {
                'id': share.id,
                'shared_with': share.user.get_full_name() if share.user else share.external_email,
                'share_type': share.share_type,
                'permission': share.permission_type,
                'created_at': share.created_at,
                'access_count': share.access_count,
                'download_count': share.download_count
            }
            for share in obj.shares.all()
        ]
    
    def get_access_log(self, obj):
        """Get recent access log"""
        # This would require a separate access log model
        return []


class DocumentUploadSerializer(serializers.Serializer):
    """Serializer for document upload"""
    
    file = serializers.FileField()
    title = serializers.CharField(max_length=255, required=False)
    description = serializers.CharField(required=False, allow_blank=True)
    document_type = serializers.ChoiceField(
        choices=Document.DOCUMENT_TYPES,
        default='OTHER'
    )
    category = serializers.PrimaryKeyRelatedField(
        queryset=DocumentCategory.objects.all(),
        required=False
    )
    access_level = serializers.ChoiceField(
        choices=Document.ACCESS_LEVELS,
        default='PRIVATE'
    )
    tags = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        default=list
    )
    
    # Related object
    content_type_id = serializers.IntegerField(required=False)
    object_id = serializers.CharField(required=False)
    
    def validate_file(self, value):
        """Validate uploaded file"""
        # Check file size (10MB limit)
        if value.size > 10 * 1024 * 1024:
            raise serializers.ValidationError("File size cannot exceed 10MB")
        
        # Check file type
        allowed_types = [
            'application/pdf', 'application/msword', 'application/vnd.ms-excel',
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            'image/jpeg', 'image/png', 'image/gif', 'text/plain'
        ]
        
        if value.content_type not in allowed_types:
            raise serializers.ValidationError("File type not supported")
        
        return value
    
    def validate(self, data):
        """Validate document data"""
        # If no title provided, use filename
        if not data.get('title'):
            data['title'] = data['file'].name
        
        return data


class DocumentBulkActionSerializer(serializers.Serializer):
    """Serializer for bulk document actions"""
    
    document_ids = serializers.ListField(
        child=serializers.IntegerField(),
        min_length=1
    )
    action = serializers.ChoiceField(choices=[
        ('move_category', 'Move to Category'),
        ('change_access', 'Change Access Level'),
        ('add_tags', 'Add Tags'),
        ('remove_tags', 'Remove Tags'),
        ('archive', 'Archive'),
        ('delete', 'Delete')
    ])
    
    # Action parameters
    target_category = serializers.PrimaryKeyRelatedField(
        queryset=DocumentCategory.objects.all(),
        required=False
    )
    access_level = serializers.ChoiceField(
        choices=Document.ACCESS_LEVELS,
        required=False
    )
    tags = serializers.ListField(
        child=serializers.CharField(),
        required=False
    )
    
    def validate(self, data):
        """Validate bulk action data"""
        action = data.get('action')
        
        if action == 'move_category' and not data.get('target_category'):
            raise serializers.ValidationError({
                'target_category': 'Required for move_category action'
            })
        
        if action == 'change_access' and not data.get('access_level'):
            raise serializers.ValidationError({
                'access_level': 'Required for change_access action'
            })
        
        if action in ['add_tags', 'remove_tags'] and not data.get('tags'):
            raise serializers.ValidationError({
                'tags': f'Required for {action} action'
            })
        
        return data
    
    def validate_document_ids(self, value):
        """Validate document IDs"""
        tenant = self.context['request'].user.tenant
        existing_docs = Document.objects.filter(
            tenant=tenant,
            id__in=value,
            is_active=True
        ).count()
        
        if existing_docs != len(value):
            raise serializers.ValidationError("Some document IDs are invalid")
        
        return value