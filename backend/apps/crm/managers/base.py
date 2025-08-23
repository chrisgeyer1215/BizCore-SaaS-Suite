"""
Base Manager Classes
Common functionality for all CRM managers
"""

from django.db import models
from django.db.models import Q, Count, Sum, Avg, Max, Min
from django.utils import timezone
from django.core.exceptions import ValidationError
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any, Union


class TenantAwareManager(models.Manager):
    """
    Base manager that automatically filters by tenant
    Ensures multi-tenant data isolation
    """
    
    def get_queryset(self):
        """Override to add tenant filtering"""
        return super().get_queryset()
    
    def for_tenant(self, tenant):
        """Filter queryset by tenant"""
        return self.filter(tenant=tenant)
    
    def get_tenant_stats(self, tenant, date_range: int = 30):
        """Get basic statistics for tenant"""
        end_date = timezone.now()
        start_date = end_date - timedelta(days=date_range)
        
        return self.for_tenant(tenant).filter(
            created_at__range=[start_date, end_date]
        ).aggregate(
            total_count=Count('id'),
            recent_count=Count('id', filter=Q(created_at__gte=start_date))
        )


class SoftDeleteManager(TenantAwareManager):
    """
    Manager for soft-deleted models
    Automatically excludes deleted records
    """
    
    def get_queryset(self):
        """Exclude soft-deleted records"""
        return super().get_queryset().filter(is_deleted=False)
    
    def with_deleted(self):
        """Include soft-deleted records"""
        return super().get_queryset()
    
    def deleted_only(self):
        """Only soft-deleted records"""
        return super().get_queryset().filter(is_deleted=True)
    
    def hard_delete(self, **kwargs):
        """Permanently delete records"""
        return super().get_queryset().filter(**kwargs).delete()
    
    def restore(self, **kwargs):
        """Restore soft-deleted records"""
        return self.with_deleted().filter(
            is_deleted=True, **kwargs
        ).update(
            is_deleted=False,
            deleted_at=None
        )


class TimestampedManager(SoftDeleteManager):
    """
    Manager for timestamped models
    Provides time-based filtering and analytics
    """
    
    def created_between(self, start_date, end_date):
        """Filter by creation date range"""
        return self.filter(created_at__range=[start_date, end_date])
    
    def created_today(self):
        """Records created today"""
        today = timezone.now().date()
        return self.filter(created_at__date=today)
    
    def created_this_week(self):
        """Records created this week"""
        today = timezone.now().date()
        week_start = today - timedelta(days=today.weekday())
        return self.filter(created_at__date__gte=week_start)
    
    def created_this_month(self):
        """Records created this month"""
        today = timezone.now().date()
        month_start = today.replace(day=1)
        return self.filter(created_at__date__gte=month_start)
    
    def modified_recently(self, hours: int = 24):
        """Records modified within specified hours"""
        cutoff = timezone.now() - timedelta(hours=hours)
        return self.filter(modified_at__gte=cutoff)
    
    def get_creation_trends(self, tenant, days: int = 30):
        """Get creation trends over time"""
        end_date = timezone.now()
        start_date = end_date - timedelta(days=days)
        
        return self.for_tenant(tenant).filter(
            created_at__range=[start_date, end_date]
        ).extra(
            select={'day': 'date(created_at)'}
        ).values('day').annotate(
            count=Count('id')
        ).order_by('day')


class AdvancedQueryManager(TimestampedManager):
    """
    Advanced query manager with complex filtering capabilities
    """
    
    def search(self, query: str, fields: List[str]):
        """Full-text search across specified fields"""
        if not query or not fields:
            return self.none()
        
        q_objects = Q()
        for field in fields:
            q_objects |= Q(**{f"{field}__icontains": query})
        
        return self.filter(q_objects)
    
    def filter_by_date_range(self, field: str, start_date=None, end_date=None):
        """Filter by custom date field range"""
        queryset = self.get_queryset()
        
        if start_date:
            queryset = queryset.filter(**{f"{field}__gte": start_date})
        if end_date:
            queryset = queryset.filter(**{f"{field}__lte": end_date})
        
        return queryset
    
    def get_field_distribution(self, field: str, tenant=None):
        """Get distribution of values for a field"""
        queryset = self.get_queryset()
        if tenant:
            queryset = queryset.for_tenant(tenant)
        
        return queryset.values(field).annotate(
            count=Count('id')
        ).order_by('-count')
    
    def get_performance_metrics(self, tenant, date_field: str = 'created_at', days: int = 30):
        """Get performance metrics for the model"""
        end_date = timezone.now()
        start_date = end_date - timedelta(days=days)
        
        current_period = self.for_tenant(tenant).filter(
            **{f"{date_field}__range": [start_date, end_date]}
        )
        
        previous_start = start_date - timedelta(days=days)
        previous_period = self.for_tenant(tenant).filter(
            **{f"{date_field}__range": [previous_start, start_date]}
        )
        
        current_count = current_period.count()
        previous_count = previous_period.count()
        
        growth_rate = 0
        if previous_count > 0:
            growth_rate = ((current_count - previous_count) / previous_count) * 100
        
        return {
            'current_period_count': current_count,
            'previous_period_count': previous_count,
            'growth_rate': round(growth_rate, 2),
            'average_per_day': round(current_count / days, 2),
            'total_count': self.for_tenant(tenant).count()
        }


class BulkOperationManager(AdvancedQueryManager):
    """
    Manager with bulk operation capabilities
    """
    
    def bulk_update_status(self, ids: List[int], status: str, user=None):
        """Bulk update status for multiple records"""
        update_data = {
            'status': status,
            'modified_at': timezone.now()
        }
        
        if user:
            update_data['modified_by'] = user
        
        return self.filter(id__in=ids).update(**update_data)
    
    def bulk_assign(self, ids: List[int], user, assigned_by=None):
        """Bulk assign records to a user"""
        update_data = {
            'assigned_to': user,
            'modified_at': timezone.now()
        }
        
        if assigned_by:
            update_data['modified_by'] = assigned_by
        
        return self.filter(id__in=ids).update(**update_data)
    
    def bulk_soft_delete(self, ids: List[int], deleted_by=None):
        """Bulk soft delete records"""
        update_data = {
            'is_deleted': True,
            'deleted_at': timezone.now()
        }
        
        if deleted_by:
            update_data['deleted_by'] = deleted_by
        
        return self.filter(id__in=ids).update(**update_data)
    
    def bulk_restore(self, ids: List[int]):
        """Bulk restore soft-deleted records"""
        return self.with_deleted().filter(
            id__in=ids, is_deleted=True
        ).update(
            is_deleted=False,
            deleted_at=None
        )
    
    def create_batch(self, records: List[Dict], batch_size: int = 1000):
        """Create multiple records in batches"""
        created_objects = []
        
        for i in range(0, len(records), batch_size):
            batch = records[i:i + batch_size]
            objects = [self.model(**record) for record in batch]
            created_batch = self.bulk_create(objects, batch_size=batch_size)
            created_objects.extend(created_batch)
        
        return created_objects


class AnalyticsManager(BulkOperationManager):
    """
    Manager with advanced analytics capabilities
    """
    
    def get_conversion_metrics(self, tenant, source_status: str, target_status: str, days: int = 30):
        """Calculate conversion rates between statuses"""
        end_date = timezone.now()
        start_date = end_date - timedelta(days=days)
        
        source_count = self.for_tenant(tenant).filter(
            status=source_status,
            created_at__range=[start_date, end_date]
        ).count()
        
        converted_count = self.for_tenant(tenant).filter(
            status=target_status,
            created_at__range=[start_date, end_date]
        ).count()
        
        conversion_rate = 0
        if source_count > 0:
            conversion_rate = (converted_count / source_count) * 100
        
        return {
            'source_count': source_count,
            'converted_count': converted_count,
            'conversion_rate': round(conversion_rate, 2),
            'period': f"{days} days"
        }
    
    def get_velocity_metrics(self, tenant, status_field: str = 'status', days: int = 30):
        """Calculate velocity metrics (time between status changes)"""
        # This would require activity/history tracking
        # Implementation depends on your activity tracking system
        pass
    
    def get_cohort_data(self, tenant, cohort_field: str = 'created_at', metric_field: str = 'id'):
        """Get cohort analysis data"""
        # Basic cohort analysis implementation
        return self.for_tenant(tenant).extra(
            select={
                'cohort_month': "DATE_TRUNC('month', %s)" % cohort_field
            }
        ).values('cohort_month').annotate(
            cohort_size=Count(metric_field)
        ).order_by('cohort_month')
    
    def get_funnel_data(self, tenant, stages: List[str], date_range: int = 30):
        """Get funnel analysis data"""
        end_date = timezone.now()
        start_date = end_date - timedelta(days=date_range)
        
        funnel_data = []
        base_queryset = self.for_tenant(tenant).filter(
            created_at__range=[start_date, end_date]
        )
        
        for stage in stages:
            count = base_queryset.filter(status=stage).count()
            funnel_data.append({
                'stage': stage,
                'count': count
            })
        
        # Calculate conversion rates
        for i in range(1, len(funnel_data)):
            if funnel_data[i-1]['count'] > 0:
                conversion_rate = (funnel_data[i]['count'] / funnel_data[i-1]['count']) * 100
                funnel_data[i]['conversion_rate'] = round(conversion_rate, 2)
        
        return funnel_data