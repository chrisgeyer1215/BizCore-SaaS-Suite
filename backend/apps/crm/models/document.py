# ============================================================================
# backend/apps/crm/models/document.py - Document Management Models
# ============================================================================

from django.db import models
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey
from django.utils import timezone
from django.core.exceptions import ValidationError
import secrets
import os

from apps.core.models import TenantBaseModel, SoftDeleteMixin

User = get_user_model()


class DocumentCategory(TenantBaseModel, SoftDeleteMixin):
    """Enhanced document organization categories"""
    
    # Category Information
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    color = models.CharField(max_length=7, default='#007bff')  # Hex color
    icon = models.CharField(max_length=50, blank=True)
    
    # Hierarchy
    parent = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='subcategories'
    )
    level = models.PositiveSmallIntegerField(default=0)
    
    # Access Control
    is_public = models.BooleanField(default=True)
    restricted_access = models.BooleanField(default=False)
    allowed_users = models.ManyToManyField(
        User,
        blank=True,
        related_name='allowed_document_categories'
    )
    
    # Storage Configuration
    max_file_size_mb = models.IntegerField(default=10)
    allowed_file_types = models.JSONField(default=list)
    require_approval = models.BooleanField(default=False)
    
    # Performance Metrics
    total_documents = models.IntegerField(default=0)
    total_size_bytes = models.BigIntegerField(default=0)
    
    # Settings
    is_active = models.BooleanField(default=True)
    sort_order = models.IntegerField(default=0)
    
    class Meta:
        ordering = ['sort_order', 'name']
        verbose_name_plural = 'Document Categories'
        constraints = [
            models.UniqueConstraint(
                fields=['tenant', 'name'],
                name='unique_tenant_document_category'
            ),
        ]
        
    def __str__(self):
        return self.name
    
    def save(self, *args, **kwargs):
        # Auto-calculate level based on parent
        if self.parent:
            self.level = self.parent.level + 1
        else:
            self.level = 0
        super().save(*args, **kwargs)


class Document(TenantBaseModel, SoftDeleteMixin):
    """Enhanced file storage with metadata and collaboration"""
    
    DOCUMENT_TYPES = [
        ('CONTRACT', 'Contract'),
        ('PROPOSAL', 'Proposal'),
        ('PRESENTATION', 'Presentation'),
        ('SPREADSHEET', 'Spreadsheet'),
        ('IMAGE', 'Image'),
        ('VIDEO', 'Video'),
        ('AUDIO', 'Audio'),
        ('PDF', 'PDF Document'),
        ('TEMPLATE', 'Template'),
        ('OTHER', 'Other'),
    ]
    
    ACCESS_LEVELS = [
        ('PRIVATE', 'Private'),
        ('TEAM', 'Team'),
        ('COMPANY', 'Company'),
        ('PUBLIC', 'Public'),
    ]
    
    # Document Information
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    document_type = models.CharField(max_length=20, choices=DOCUMENT_TYPES, default='OTHER')
    
    # File Information
    file_name = models.CharField(max_length=255)
    file_path = models.CharField(max_length=500)
    file_size = models.BigIntegerField()  # Size in bytes
    mime_type = models.CharField(max_length=100)
    file_hash = models.CharField(max_length=64, blank=True)  # SHA-256 hash
    
    # Versioning
    version = models.CharField(max_length=20, default='1.0')
    is_current_version = models.BooleanField(default=True)
    parent_document = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='versions'
    )
    
    # Organization
    category = models.ForeignKey(
        DocumentCategory,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='documents'
    )
    tags = models.JSONField(default=list)
    
    # Generic Relation to CRM Entities
    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        null=True,
        blank=True
    )
    object_id = models.CharField(max_length=36, null=True, blank=True)
    related_to = GenericForeignKey('content_type', 'object_id')
    
    # Access Control
    access_level = models.CharField(max_length=15, choices=ACCESS_LEVELS, default='PRIVATE')
    owner = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='owned_documents'
    )
    
    # Approval Workflow
    requires_approval = models.BooleanField(default=False)
    is_approved = models.BooleanField(default=True)
    approved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_documents'
    )
    approved_date = models.DateTimeField(null=True, blank=True)
    
    # Tracking
    download_count = models.IntegerField(default=0)
    view_count = models.IntegerField(default=0)
    last_accessed = models.DateTimeField(null=True, blank=True)
    last_accessed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='last_accessed_documents'
    )
    
    # Security
    is_encrypted = models.BooleanField(default=False)
    password_protected = models.BooleanField(default=False)
    
    # External Integration
    external_url = models.URLField(blank=True)
    cloud_storage_id = models.CharField(max_length=255, blank=True)
    cloud_storage_provider = models.CharField(max_length=50, blank=True)
    
    # Expiration
    expires_at = models.DateTimeField(null=True, blank=True)
    auto_delete_on_expiry = models.BooleanField(default=False)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['tenant', 'content_type', 'object_id']),
            models.Index(fields=['tenant', 'category', 'document_type']),
            models.Index(fields=['tenant', 'owner']),
            models.Index(fields=['tenant', 'file_name']),
            models.Index(fields=['tenant', 'is_current_version']),
        ]
        
    def __str__(self):
        return self.title
    
    def save(self, *args, **kwargs):
        # Generate file hash if not provided
        if not self.file_hash and self.file_path:
            import hashlib
            try:
                with open(self.file_path, 'rb') as f:
                    file_hash = hashlib.sha256()
                    for chunk in iter(lambda: f.read(4096), b""):
                        file_hash.update(chunk)
                    self.file_hash = file_hash.hexdigest()
            except FileNotFoundError:
                pass
        
        super().save(*args, **kwargs)
    
    def create_new_version(self, file_path, file_name, updated_by):
        """Create a new version of this document"""
        # Mark current versions as not current
        Document.objects.filter(
            tenant=self.tenant,
            parent_document=self.parent_document or self
        ).update(is_current_version=False)
        
        # Create new version
        new_version = Document.objects.create(
            tenant=self.tenant,
            title=self.title,
            description=self.description,
            document_type=self.document_type,
            file_name=file_name,
            file_path=file_path,
            file_size=os.path.getsize(file_path),
            mime_type=self.mime_type,
            category=self.category,
            tags=self.tags,
            content_type=self.content_type,
            object_id=self.object_id,
            access_level=self.access_level,
            owner=self.owner,
            parent_document=self.parent_document or self,
            version=self.increment_version(),
            is_current_version=True,
            created_by=updated_by,
            updated_by=updated_by
        )
        
        return new_version
    
    def increment_version(self):
        """Increment version number"""
        try:
            major, minor = map(int, self.version.split('.'))
            return f"{major}.{minor + 1}"
        except (ValueError, AttributeError):
            return "1.1"
    
    def track_access(self, user):
        """Track document access"""
        self.view_count += 1
        self.last_accessed = timezone.now()
        self.last_accessed_by = user
        self.save(update_fields=['view_count', 'last_accessed', 'last_accessed_by'])
    
    def track_download(self, user):
        """Track document download"""
        self.download_count += 1
        self.last_accessed = timezone.now()
        self.last_accessed_by = user
        self.save(update_fields=['download_count', 'last_accessed', 'last_accessed_by'])


class DocumentShare(TenantBaseModel):
    """Enhanced document sharing with granular permissions"""
    
    PERMISSION_TYPES = [
        ('VIEW', 'View Only'),
        ('DOWNLOAD', 'View & Download'),
        ('COMMENT', 'View, Download & Comment'),
        ('EDIT', 'Edit'),
        ('ADMIN', 'Full Admin'),
    ]
    
    SHARE_TYPES = [
        ('USER', 'Specific User'),
        ('TEAM', 'Team'),
        ('ROLE', 'Role'),
        ('PUBLIC_LINK', 'Public Link'),
        ('EXTERNAL_EMAIL', 'External Email'),
    ]
    
    document = models.ForeignKey(
        Document,
        on_delete=models.CASCADE,
        related_name='shares'
    )
    
    # Sharing Details
    share_type = models.CharField(max_length=20, choices=SHARE_TYPES)
    permission_type = models.CharField(max_length=15, choices=PERMISSION_TYPES, default='VIEW')
    
    # Recipients
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='document_shares'
    )
    team = models.ForeignKey(
        'Team',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='document_shares'
    )
    external_email = models.EmailField(blank=True)
    
    # Public Link Settings
    public_token = models.CharField(max_length=255, blank=True, unique=True)
    password_required = models.BooleanField(default=False)
    share_password = models.CharField(max_length=255, blank=True)
    
    # Expiration
    expires_at = models.DateTimeField(null=True, blank=True)
    max_downloads = models.IntegerField(null=True, blank=True)
    download_count = models.IntegerField(default=0)
    
    # Tracking
    last_accessed = models.DateTimeField(null=True, blank=True)
    access_count = models.IntegerField(default=0)
    
    # Notifications
    notify_on_access = models.BooleanField(default=False)
    notify_on_download = models.BooleanField(default=False)
    
    class Meta:
        indexes = [
            models.Index(fields=['tenant', 'document', 'share_type']),
            models.Index(fields=['tenant', 'user']),
            models.Index(fields=['tenant', 'public_token']),
        ]
        
    def __str__(self):
        if self.user:
            recipient = self.user.get_full_name()
        elif self.team:
            recipient = self.team.name
        elif self.external_email:
            recipient = self.external_email
        else:
            recipient = 'Public Link'
        
        return f'{self.document.title} shared with {recipient}'
    
    def save(self, *args, **kwargs):
        # Generate public token for public links
        if self.share_type == 'PUBLIC_LINK' and not self.public_token:
            self.public_token = secrets.token_urlsafe(32)
        
        super().save(*args, **kwargs)
    
    def is_valid(self):
        """Check if share is still valid"""
        if self.expires_at and timezone.now() > self.expires_at:
            return False
        
        if self.max_downloads and self.download_count >= self.max_downloads:
            return False
        
        return True
    
    def track_access(self):
        """Track share access"""
        self.access_count += 1
        self.last_accessed = timezone.now()
        self.save(update_fields=['access_count', 'last_accessed'])
    
    def track_download(self):
        """Track share download"""
        self.download_count += 1
        self.last_accessed = timezone.now()
        self.save(update_fields=['download_count', 'last_accessed'])