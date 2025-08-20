from django.db import models
from django.utils import timezone

class TimestampedMixin(models.Model):
    """
    Basic timestamp mixin
    """
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True, db_index=True)
    
    class Meta:
        abstract = True

class CreatedUpdatedMixin(TimestampedMixin):
    """
    Extended timestamp mixin with additional tracking
    """
    last_accessed_at = models.DateTimeField(null=True, blank=True)
    access_count = models.PositiveIntegerField(default=0)
    
    class Meta:
        abstract = True
        indexes = [
            models.Index(fields=['last_accessed_at']),
        ]
    
    def mark_accessed(self):
        """Mark the object as accessed"""
        self.last_accessed_at = timezone.now()
        self.access_count += 1
        self.save(update_fields=['last_accessed_at', 'access_count'])