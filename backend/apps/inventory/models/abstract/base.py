from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.db.models import Q

User = get_user_model()

class TenantBaseModel(models.Model):
    """
    Base model for all multi-tenant inventory models
    """
    tenant = models.ForeignKey(
        'core.Tenant',  # Assuming you have a core app with Tenant model
        on_delete=models.CASCADE,
        related_name='%(app_label)s_%(class)s_objects'
    )
    
    class Meta:
        abstract = True
        indexes = [
            models.Index(fields=['tenant']),
        ]
    
    def save(self, *args, **kwargs):
        # Ensure tenant is set for all saves
        if not self.tenant_id and hasattr(self, '_current_tenant'):
            self.tenant = self._current_tenant
        super().save(*args, **kwargs)

class SoftDeleteMixin(models.Model):
    """
    Mixin to provide soft delete functionality
    """
    is_deleted = models.BooleanField(default=False, db_index=True)
    deleted_at = models.DateTimeField(null=True, blank=True)
    deleted_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='%(app_label)s_%(class)s_deleted'
    )
    
    class Meta:
        abstract = True
        indexes = [
            models.Index(fields=['is_deleted', 'deleted_at']),
        ]
    
    def delete(self, soft=True, user=None):
        if soft:
            self.is_deleted = True
            self.deleted_at = timezone.now()
            if user:
                self.deleted_by = user
            self.save(update_fields=['is_deleted', 'deleted_at', 'deleted_by'])
        else:
            super().delete()
    
    def restore(self):
        """Restore a soft-deleted object"""
        self.is_deleted = False
        self.deleted_at = None
        self.deleted_by = None
        self.save(update_fields=['is_deleted', 'deleted_at', 'deleted_by'])
    
    @classmethod
    def get_active(cls):
        """Get queryset of non-deleted objects"""
        return cls.objects.filter(is_deleted=False)
    
    @classmethod
    def get_deleted(cls):
        """Get queryset of deleted objects"""
        return cls.objects.filter(is_deleted=True)