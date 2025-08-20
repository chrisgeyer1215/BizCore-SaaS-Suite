from django.db import models
from django.db.models import QuerySet
from django.core.cache import cache
from django.utils import timezone

class TenantQuerySet(QuerySet):
    """
    Custom queryset with tenant-aware operations
    """
    
    def for_tenant(self, tenant):
        """Filter by tenant"""
        return self.filter(tenant=tenant)
    
    def active(self):
        """Get active records"""
        return self.filter(is_active=True) if hasattr(self.model, 'is_active') else self
    
    def not_deleted(self):
        """Get non-deleted records (for soft delete models)"""
        return self.filter(is_deleted=False) if hasattr(self.model, 'is_deleted') else self
    
    def created_between(self, start_date, end_date):
        """Filter by creation date range"""
        return self.filter(created_at__range=[start_date, end_date])
    
    def updated_since(self, since_date):
        """Filter by update date"""
        return self.filter(updated_at__gte=since_date)
    
    def with_statistics(self):
        """Add common statistics annotations"""
        return self.annotate(
            total_count=Count('id'),
            created_this_month=Count(
                'id',
                filter=models.Q(created_at__month=timezone.now().month)
            )
        )

class TenantManager(models.Manager):
    """
    Manager that uses TenantQuerySet
    """
    
    def get_queryset(self):
        return TenantQuerySet(self.model, using=self._db)
    
    def for_tenant(self, tenant):
        return self.get_queryset().for_tenant(tenant)
    
    def active(self):
        return self.get_queryset().active()
    
    def not_deleted(self):
        return self.get_queryset().not_deleted()
    
    def created_between(self, start_date, end_date):
        return self.get_queryset().created_between(start_date, end_date)
    
    def updated_since(self, since_date):
        return self.get_queryset().updated_since(since_date)
    
    def with_statistics(self):
        return self.get_queryset().with_statistics()