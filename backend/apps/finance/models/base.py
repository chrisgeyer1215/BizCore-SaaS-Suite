"""
Abstract base models for inventory module
Handles multi-tenant architecture and common functionality
"""
from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.core.exceptions import ValidationError
from django_tenants.models import TenantMixin
import uuid

User = get_user_model()


class TenantBaseModel(models.Model):
    """
    Base model for all tenant-aware models in inventory system
    Automatically handles tenant filtering and common fields
    """
    # Tenant reference (no FK due to cross-schema nature)
    tenant_id = models.PositiveIntegerField(
        help_text="Tenant ID for multi-tenant isolation"
    )
    
    # Common timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # UUID for external references and API
    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    
    class Meta:
        abstract = True
        indexes = [
            models.Index(fields=['tenant_id', 'created_at']),
            models.Index(fields=['tenant_id', 'updated_at']),
        ]
    
    def clean(self):
        """Validate tenant_id is provided"""
        if not self.tenant_id:
            raise ValidationError("Tenant ID is required")
    
    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


class SoftDeleteMixin(models.Model):
    """
    Soft delete functionality for models
    """
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)
    deleted_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='%(class)s_deleted_items'
    )
    
    class Meta:
        abstract = True
    
    def delete(self, *args, **kwargs):
        """Soft delete the instance"""
        self.is_deleted = True
        self.deleted_at = timezone.now()
        # deleted_by should be set by the calling code
        self.save(update_fields=['is_deleted', 'deleted_at', 'deleted_by'])
    
    def hard_delete(self, *args, **kwargs):
        """Permanently delete the instance"""
        super().delete(*args, **kwargs)
    
    def restore(self):
        """Restore soft deleted instance"""
        self.is_deleted = False
        self.deleted_at = None
        self.deleted_by = None
        self.save(update_fields=['is_deleted', 'deleted_at', 'deleted_by'])


class AuditableMixin(models.Model):
    """
    Audit trail functionality for tracking changes
    """
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='%(class)s_created_items'
    )
    updated_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='%(class)s_updated_items'
    )
    
    class Meta:
        abstract = True


class ActivatableMixin(models.Model):
    """
    Mixin for models that can be activated/deactivated
    """
    is_active = models.BooleanField(default=True)
    activated_at = models.DateTimeField(null=True, blank=True)
    deactivated_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        abstract = True
    
    def activate(self):
        """Activate the instance"""
        self.is_active = True
        self.activated_at = timezone.now()
        self.deactivated_at = None
        self.save(update_fields=['is_active', 'activated_at', 'deactivated_at'])
    
    def deactivate(self):
        """Deactivate the instance"""
        self.is_active = False
        self.deactivated_at = timezone.now()
        self.save(update_fields=['is_active', 'deactivated_at'])


class OrderableMixin(models.Model):
    """
    Mixin for models that need ordering/sorting
    """
    sort_order = models.PositiveIntegerField(default=0)
    
    class Meta:
        abstract = True
        ordering = ['sort_order']