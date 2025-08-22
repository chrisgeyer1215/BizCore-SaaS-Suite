from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.db.models import Q

User = get_user_model()

class ActivatableMixin(models.Model):
    """
    Mixin to provide activation/deactivation functionality
    """
    is_active = models.BooleanField(default=True, db_index=True)
    
    class Meta:
        abstract = True
    
    def activate(self):
        """Activate the object"""
        self.is_active = True
        self.save(update_fields=['is_active'])
    
    def deactivate(self):
        """Deactivate the object"""
        self.is_active = False
        self.save(update_fields=['is_active'])
    
    @classmethod
    def get_active(cls):
        """Get queryset of active objects"""
        return cls.objects.filter(is_active=True)
    
    @classmethod
    def get_inactive(cls):
        """Get queryset of inactive objects"""
        return cls.objects.filter(is_active=False)

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


class OrderableMixin(models.Model):
    """
    Mixin for models that need ordering/sorting
    """
    sort_order = models.PositiveIntegerField(default=0)
    
    class Meta:
        abstract = True
        ordering = ['sort_order']