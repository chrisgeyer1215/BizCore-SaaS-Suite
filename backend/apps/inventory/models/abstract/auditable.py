from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.contrib.contenttypes.models import ContentType
import json

User = get_user_model()

class AuditableMixin(models.Model):
    """
    Mixin to provide basic audit trail functionality
    """
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True, db_index=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='%(app_label)s_%(class)s_created'
    )
    updated_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='%(app_label)s_%(class)s_updated'
    )
    
    class Meta:
        abstract = True
        indexes = [
            models.Index(fields=['created_at']),
            models.Index(fields=['updated_at']),
        ]
    
    def save(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        if user:
            if not self.pk:
                self.created_by = user
            self.updated_by = user
        super().save(*args, **kwargs)

class FullAuditMixin(AuditableMixin):
    """
    Extended audit mixin with change tracking
    """
    version = models.PositiveIntegerField(default=1)
    
    class Meta:
        abstract = True
    
    def save(self, *args, **kwargs):
        if self.pk:
            # Check if any fields changed
            old_instance = self.__class__.objects.get(pk=self.pk)
            if self._has_changed(old_instance):
                self.version += 1
                # Create audit log entry
                self._create_audit_log(old_instance, kwargs.get('user'))
        super().save(*args, **kwargs)
    
    def _has_changed(self, old_instance):
        """Check if any auditable fields have changed"""
        exclude_fields = ['updated_at', 'version']
        for field in self._meta.fields:
            if field.name in exclude_fields:
                continue
            if getattr(self, field.name) != getattr(old_instance, field.name):
                return True
        return False
    
    def _create_audit_log(self, old_instance, user):
        """Create audit log entry"""
        from ..core.audit import AuditLog  # Import here to avoid circular imports
        
        changes = {}
        for field in self._meta.fields:
            old_value = getattr(old_instance, field.name)
            new_value = getattr(self, field.name)
            if old_value != new_value:
                changes[field.name] = {
                    'old': str(old_value) if old_value is not None else None,
                    'new': str(new_value) if new_value is not None else None
                }
        
        if changes:
            AuditLog.objects.create(
                tenant=self.tenant,
                content_type=ContentType.objects.get_for_model(self),
                object_id=self.pk,
                action='UPDATE',
                changes=json.dumps(changes),
                user=user,
                timestamp=timezone.now()
            )

class AuditLog(models.Model):
    """
    Model to store audit trail information
    """
    tenant = models.ForeignKey(
        'core.Tenant',
        on_delete=models.CASCADE,
        related_name='audit_logs'
    )
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    action = models.CharField(max_length=20, choices=[
        ('CREATE', 'Create'),
        ('UPDATE', 'Update'),
        ('DELETE', 'Delete'),
        ('RESTORE', 'Restore'),
    ])
    changes = models.JSONField(default=dict)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['tenant', 'content_type', 'object_id']),
            models.Index(fields=['timestamp']),
            models.Index(fields=['user', 'timestamp']),
        ]
    
    def __str__(self):
        return f"{self.action} on {self.content_type} by {self.user}"