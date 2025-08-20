from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
import json

User = get_user_model()

class ChangeTrackableMixin(models.Model):
    """
    Mixin to track field changes
    """
    change_log = models.JSONField(default=list, blank=True)
    last_changed_fields = models.JSONField(default=list, blank=True)
    
    class Meta:
        abstract = True
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._original_values = {}
        if self.pk:
            self._store_original_values()
    
    def _store_original_values(self):
        """Store original field values for change tracking"""
        for field in self._meta.fields:
            if not isinstance(field, (models.DateTimeField, models.AutoField)):
                self._original_values[field.name] = getattr(self, field.name)
    
    def save(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        if self.pk:
            self._track_changes(user)
        super().save(*args, **kwargs)
        if self.pk:
            self._store_original_values()
    
    def _track_changes(self, user=None):
        """Track field changes"""
        changes = []
        changed_fields = []
        
        for field_name, old_value in self._original_values.items():
            new_value = getattr(self, field_name)
            if old_value != new_value:
                changes.append({
                    'field': field_name,
                    'old_value': str(old_value) if old_value is not None else None,
                    'new_value': str(new_value) if new_value is not None else None,
                    'changed_at': timezone.now().isoformat(),
                    'changed_by': user.username if user else None
                })
                changed_fields.append(field_name)
        
        if changes:
            # Keep only last 100 changes
            current_log = self.change_log or []
            current_log.extend(changes)
            self.change_log = current_log[-100:]
            self.last_changed_fields = changed_fields

class StatusTrackableMixin(models.Model):
    """
    Mixin to track status changes with history
    """
    status_history = models.JSONField(default=list, blank=True)
    previous_status = models.CharField(max_length=50, blank=True)
    status_changed_at = models.DateTimeField(null=True, blank=True)
    status_changed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='%(app_label)s_%(class)s_status_changes'
    )
    
    class Meta:
        abstract = True
    
    def change_status(self, new_status, user=None, reason=None):
        """Change status with tracking"""
        if hasattr(self, 'status') and self.status != new_status:
            # Store previous status
            self.previous_status = self.status
            self.status_changed_at = timezone.now()
            self.status_changed_by = user
            
            # Add to history
            history_entry = {
                'from_status': self.status,
                'to_status': new_status,
                'changed_at': timezone.now().isoformat(),
                'changed_by': user.username if user else None,
                'reason': reason
            }
            
            current_history = self.status_history or []
            current_history.append(history_entry)
            # Keep only last 50 status changes
            self.status_history = current_history[-50:]
            
            # Update status
            self.status = new_status
    
    def get_status_duration(self):
        """Get duration in current status"""
        if self.status_changed_at:
            return timezone.now() - self.status_changed_at
        return timezone.now() - self.created_at if hasattr(self, 'created_at') else None