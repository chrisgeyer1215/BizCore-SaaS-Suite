"""
Base manager classes for inventory models
Handles tenant-aware querying and common operations
"""
from django.db import models
from django.core.exceptions import ValidationError


class TenantAwareManager(models.Manager):
    """
    Manager that automatically filters by tenant_id
    """
    
    def get_queryset(self):
        """Override to add tenant filtering if context available"""
        qs = super().get_queryset()
        # Tenant filtering will be handled at view level
        # due to cross-schema nature of django-tenants
        return qs
    
    def for_tenant(self, tenant_id):
        """Explicitly filter by tenant"""
        return self.filter(tenant_id=tenant_id)
    
    def active(self):
        """Get only active records"""
        return self.filter(is_active=True)
    
    def inactive(self):
        """Get only inactive records"""
        return self.filter(is_active=False)


class SoftDeleteManager(TenantAwareManager):
    """
    Manager that excludes soft-deleted items by default
    """
    
    def get_queryset(self):
        """Exclude soft-deleted items"""
        return super().get_queryset().filter(is_deleted=False)
    
    def with_deleted(self):
        """Include soft-deleted items"""
        return super().get_queryset()
    
    def deleted_only(self):
        """Get only soft-deleted items"""
        return super().get_queryset().filter(is_deleted=True)


class InventoryQuerySetMixin:
    """
    Common query methods for inventory models
    """
    
    def by_code(self, code):
        """Filter by code field"""
        return self.filter(code__iexact=code)
    
    def by_name_contains(self, name):
        """Filter by name containing text"""
        return self.filter(name__icontains=name)
    
    def active_only(self):
        """Get only active records"""
        return self.filter(is_active=True)
    
    def for_date_range(self, start_date, end_date):
        """Filter by date range"""
        return self.filter(created_at__range=[start_date, end_date])


class InventoryQuerySet(models.QuerySet, InventoryQuerySetMixin):
    """
    Custom QuerySet with inventory-specific methods
    """
    pass


class InventoryManager(TenantAwareManager):
    """
    Manager with custom QuerySet
    """
    
    def get_queryset(self):
        return InventoryQuerySet(self.model, using=self._db)

class BaseInventoryManager(models.Manager):
    """
    Base manager for all inventory models with common functionality
    """
    
    def get_queryset(self):
        """Override to add default optimizations"""
        return super().get_queryset().select_related()
    
    def active(self):
        """Get active records (for models with is_active field)"""
        if hasattr(self.model, 'is_active'):
            return self.filter(is_active=True)
        return self.all()
    
    def inactive(self):
        """Get inactive records"""
        if hasattr(self.model, 'is_active'):
            return self.filter(is_active=False)
        return self.none()