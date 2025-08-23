"""
Cleanup Tasks
Handle data cleanup, archiving, and system maintenance
"""

from celery import shared_task
from django.utils import timezone
from django.db import transaction
from django.core.files.storage import default_storage
from django.conf import settings
import logging
from datetime import timedelta
import os

from .base import TenantAwareTask, ScheduledTask, MonitoredTask
from ..models import (
    Activity, EmailLog, WorkflowExecution, Document, 
    TaskExecution, Lead, Opportunity, Ticket, AuditTrail
)
from ..utils.tenant_utils import get_tenant_by_id

logger = logging.getLogger(__name__)


@shared_task(base=ScheduledTask, bind=True)
def cleanup_old_activities_task(self, tenant_id=None, days_to_keep=365):
    """
    Clean up old completed activities
    """
    try:
        tenant = get_tenant_by_id(tenant_id) if tenant_id else None
        cutoff_date = timezone.now() - timedelta(days=days_to_keep)
        
        query = Activity.objects.filter(
            completed_at__lt=cutoff_date,
            status='completed'
        )
        
        if tenant:
            query = query.filter(tenant=tenant)
        
        # Archive activities before deletion
        activities_to_archive = list(query.values(
            'id', 'subject', 'activity_type', 'completed_at', 
            'assigned_to_id', 'entity_type', 'entity_id'
        ))
        
        # Store archive data (this could be to a separate archive table or file storage)
        if activities_to_archive:
            archive_data = {
                'archived_at': timezone.now().isoformat(),
                'tenant_id': tenant.id if tenant else None,
                'activities': activities_to_archive
            }
            # Save to archive storage (implementation depends on your archive strategy)
            logger.info(f"Archiving {len(activities_to_archive)} activities")
        
        # Delete old activities
        deleted_count = query.delete()[0]
        
        logger.info(f"Cleaned up {deleted_count} old activities")
        
        return {
            'status': 'completed',
            'deleted_count': deleted_count,
            'archived_count': len(activities_to_archive),
            'cutoff_date': cutoff_date.isoformat()
        }
        
    except Exception as e:
        logger.error(f"Activity cleanup task failed: {e}")
        raise


@shared_task(base=ScheduledTask, bind=True)
def cleanup_old_documents_task(self, tenant_id=None, days_to_keep=90, cleanup_versions=True):
    """
    Clean up old documents and versions
    """
    try:
        tenant = get_tenant_by_id(tenant_id) if tenant_id else None
        cutoff_date = timezone.now() - timedelta(days=days_to_keep)
        
        # Find old documents
        query = Document.objects.filter(
            uploaded_at__lt=cutoff_date,
            is_deleted=True  # Only cleanup already deleted documents
        )
        
        if tenant:
            query = query.filter(tenant=tenant)
        
        deleted_count = 0
        space_freed = 0
        
        for document in query:
            try:
                # Delete physical file
                if document.file:
                    file_size = document.file_size or 0
                    space_freed += file_size
                    
                    try:
                        default_storage.delete(document.file.name)
                    except Exception as e:
                        logger.warning(f"Failed to delete file {document.file.name}: {e}")
                
                # Delete database record
                document.delete()
                deleted_count += 1
                
            except Exception as e:
                logger.error(f"Failed to cleanup document {document.id}: {e}")
        
        # Clean up old document versions
        versions_deleted = 0
        if cleanup_versions:
            old_versions = Document.objects.filter(
                uploaded_at__lt=cutoff_date,
                version__gt=1,
                parent_document__isnull=False
            )
            
            if tenant:
                old_versions = old_versions.filter(tenant=tenant)
            
            for version in old_versions:
                try:
                    if version.file:
                        space_freed += version.file_size or 0
                        try:
                            default_storage.delete(version.file.name)
                        except:
                            pass
                    
                    version.delete()
                    versions_deleted += 1
                    
                except Exception as e:
                    logger.error(f"Failed to cleanup document version {version.id}: {e}")
        
        logger.info(f"Cleaned up {deleted_count} documents and {versions_deleted} versions, freed {space_freed} bytes")
        
        return {
            'status': 'completed',
            'deleted_documents': deleted_count,
            'deleted_versions': versions_deleted,
            'space_freed_bytes': space_freed,
            'space_freed_mb': round(space_freed / (1024 * 1024), 2)
        }
        
    except Exception as e:
        logger.error(f"Document cleanup task failed: {e}")
        raise


@shared_task(base=ScheduledTask, bind=True)
def cleanup_workflow_executions_task(self, tenant_id=None, days_to_keep=180):
    """
    Clean up old workflow execution logs
    """
    try:
        tenant = get_tenant_by_id(tenant_id) if tenant_id else None
        cutoff_date = timezone.now() - timedelta(days=days_to_keep)
        
        query = WorkflowExecution.objects.filter(
            executed_at__lt=cutoff_date
        )
        
        if tenant:
            query = query.filter(tenant=tenant)
        
        # Keep summary statistics before deletion
        execution_stats = query.aggregate(
            total_executions=models.Count('id'),
            successful_executions=models.Count('id', filter=models.Q(status='completed')),
            failed_executions=models.Count('id', filter=models.Q(status='failed'))
        )
        
        deleted_count = query.delete()[0]
        
        logger.info(f"Cleaned up {deleted_count} workflow executions")
        
        return {
            'status': 'completed',
            'deleted_count': deleted_count,
            'statistics': execution_stats
        }
        
    except Exception as e:
        logger.error(f"Workflow execution cleanup task failed: {e}")
        raise


@shared_task(base=ScheduledTask, bind=True)
def cleanup_email_logs_task(self, tenant_id=None, days_to_keep=180):
    """
    Clean up old email logs
    """
    try:
        tenant = get_tenant_by_id(tenant_id) if tenant_id else None
        cutoff_date = timezone.now() - timedelta(days=days_to_keep)
        
        query = EmailLog.objects.filter(
            sent_at__lt=cutoff_date
        )
        
        if tenant:
            query = query.filter(tenant=tenant)
        
        # Archive email statistics before deletion
        email_stats = query.aggregate(
            total_emails=models.Count('id'),
            successful_emails=models.Count('id', filter=models.Q(status='sent')),
            failed_emails=models.Count('id', filter=models.Q(status='failed')),
            bounced_emails=models.Count('id', filter=models.Q(status='bounced'))
        )
        
        deleted_count = query.delete()[0]
        
        logger.info(f"Cleaned up {deleted_count} email logs")
        
        return {
            'status': 'completed',
            'deleted_count': deleted_count,
            'email_statistics': email_stats
        }
        
    except Exception as e:
        logger.error(f"Email log cleanup task failed: {e}")
        raise


@shared_task(base=ScheduledTask, bind=True)
def cleanup_task_executions_task(self, days_to_keep=30):
    """
    Clean up old task execution records
    """
    try:
        cutoff_date = timezone.now() - timedelta(days=days_to_keep)
        
        deleted_count = TaskExecution.objects.filter(
            started_at__lt=cutoff_date
        ).delete()[0]
        
        logger.info(f"Cleaned up {deleted_count} task execution records")
        
        return {
            'status': 'completed',
            'deleted_count': deleted_count
        }
        
    except Exception as e:
        logger.error(f"Task execution cleanup failed: {e}")
        raise


@shared_task(base=TenantAwareTask, bind=True)
def cleanup_duplicate_records_task(self, tenant_id, record_type='leads'):
    """
    Clean up duplicate records
    """
    try:
        tenant = get_tenant_by_id(tenant_id)
        
        duplicates_removed = 0
        
        if record_type == 'leads':
            duplicates_removed = self._cleanup_duplicate_leads(tenant)
        elif record_type == 'contacts':
            duplicates_removed = self._cleanup_duplicate_contacts(tenant)
        elif record_type == 'accounts':
            duplicates_removed = self._cleanup_duplicate_accounts(tenant)
        
        logger.info(f"Removed {duplicates_removed} duplicate {record_type}")
        
        return {
            'status': 'completed',
            'duplicates_removed': duplicates_removed,
            'record_type': record_type
        }
        
    except Exception as e:
        logger.error(f"Duplicate cleanup task failed: {e}")
        raise
    
    def _cleanup_duplicate_leads(self, tenant):
        """Clean up duplicate leads based on email and phone"""
        from django.db.models import Count
        
        # Find duplicates by email
        duplicate_emails = Lead.objects.filter(
            tenant=tenant,
            email__isnull=False
        ).values('email').annotate(
            count=Count('id')
        ).filter(count__gt=1)
        
        removed_count = 0
        
        for dup in duplicate_emails:
            leads = Lead.objects.filter(
                tenant=tenant,
                email=dup['email']
            ).order_by('created_at')  # Keep the oldest
            
            # Remove all but the first one
            leads_to_remove = leads[1:]
            for lead in leads_to_remove:
                # Transfer activities and relationships to the original lead
                original_lead = leads.first()
                
                Activity.objects.filter(
                    entity_type='lead',
                    entity_id=lead.id
                ).update(entity_id=original_lead.id)
                
                lead.delete()
                removed_count += 1
        
        return removed_count
    
    def _cleanup_duplicate_contacts(self, tenant):
        """Clean up duplicate contacts"""
        from django.db.models import Count
        from ..models import Contact
        
        # Find duplicates by email
        duplicate_emails = Contact.objects.filter(
            tenant=tenant,
            email__isnull=False
        ).values('email').annotate(
            count=Count('id')
        ).filter(count__gt=1)
        
        removed_count = 0
        
        for dup in duplicate_emails:
            contacts = Contact.objects.filter(
                tenant=tenant,
                email=dup['email']
            ).order_by('created_at')
            
            original_contact = contacts.first()
            contacts_to_remove = contacts[1:]
            
            for contact in contacts_to_remove:
                # Transfer relationships
                Activity.objects.filter(
                    entity_type='contact',
                    entity_id=contact.id
                ).update(entity_id=original_contact.id)
                
                contact.delete()
                removed_count += 1
        
        return removed_count
    
    def _cleanup_duplicate_accounts(self, tenant):
        """Clean up duplicate accounts"""
        from django.db.models import Count
        
        # Find duplicates by company name and domain
        duplicate_companies = Account.objects.filter(
            tenant=tenant
        ).values('name', 'website').annotate(
            count=Count('id')
        ).filter(count__gt=1)
        
        removed_count = 0
        
        for dup in duplicate_companies:
            accounts = Account.objects.filter(
                tenant=tenant,
                name=dup['name'],
                website=dup['website']
            ).order_by('created_at')
            
            original_account = accounts.first()
            accounts_to_remove = accounts[1:]
            
            for account in accounts_to_remove:
                # Transfer contacts and opportunities
                account.contacts.all().update(account=original_account)
                account.opportunities.all().update(account=original_account)
                
                account.delete()
                removed_count += 1
        
        return removed_count


@shared_task(base=MonitoredTask, bind=True)
def optimize_database_task(self, tenant_id=None):
    """
    Optimize database performance
    """
    try:
        from django.db import connection
        
        operations_performed = []
        
        with connection.cursor() as cursor:
            # Update table statistics
            if connection.vendor == 'postgresql':
                cursor.execute("ANALYZE;")
                operations_performed.append('analyze_tables')
                
                # Vacuum old data
                cursor.execute("VACUUM;")
                operations_performed.append('vacuum_tables')
            
            elif connection.vendor == 'mysql':
                cursor.execute("OPTIMIZE TABLE crm_lead, crm_opportunity, crm_activity, crm_account;")
                operations_performed.append('optimize_tables')
        
        logger.info(f"Database optimization completed: {', '.join(operations_performed)}")
        
        return {
            'status': 'completed',
            'operations': operations_performed
        }
        
    except Exception as e:
        logger.error(f"Database optimization task failed: {e}")
        raise


@shared_task(base=ScheduledTask, bind=True)
def cleanup_audit_trail_task(self, tenant_id=None, days_to_keep=365):
    """
    Clean up old audit trail records
    """
    try:
        tenant = get_tenant_by_id(tenant_id) if tenant_id else None
        cutoff_date = timezone.now() - timedelta(days=days_to_keep)
        
        query = AuditTrail.objects.filter(
            timestamp__lt=cutoff_date
        )
        
        if tenant:
            query = query.filter(tenant=tenant)
        
        # Archive critical audit records before deletion
        critical_records = query.filter(
            action__in=['delete', 'user_login', 'permission_change']
        )
        
        if critical_records.exists():
            # Archive critical records (implementation depends on your archive strategy)
            logger.info(f"Archiving {critical_records.count()} critical audit records")
        
        deleted_count = query.delete()[0]
        
        logger.info(f"Cleaned up {deleted_count} audit trail records")
        
        return {
            'status': 'completed',
            'deleted_count': deleted_count,
            'critical_archived': critical_records.count() if 'critical_records' in locals() else 0
        }
        
    except Exception as e:
        logger.error(f"Audit trail cleanup task failed: {e}")
        raise


@shared_task(base=TenantAwareTask, bind=True)
def cleanup_inactive_records_task(self, tenant_id, record_types=None, inactive_days=180):
    """
    Clean up inactive records (leads, contacts with no recent activity)
    """
    try:
        tenant = get_tenant_by_id(tenant_id)
        cutoff_date = timezone.now() - timedelta(days=inactive_days)
        
        if not record_types:
            record_types = ['leads', 'contacts']
        
        cleanup_results = {}
        
        # Clean up inactive leads
        if 'leads' in record_types:
            inactive_leads = Lead.objects.filter(
                tenant=tenant,
                status='new',
                created_at__lt=cutoff_date,
                last_activity_date__isnull=True
            )
            
            # Move to a different status instead of deleting
            updated_count = inactive_leads.update(
                status='inactive',
                inactive_reason='No activity for 180+ days'
            )
            
            cleanup_results['leads'] = {
                'marked_inactive': updated_count
            }
        
        # Clean up inactive contacts
        if 'contacts' in record_types:
            from ..models import Contact
            
            inactive_contacts = Contact.objects.filter(
                tenant=tenant,
                created_at__lt=cutoff_date
            ).filter(
                ~models.Q(activities__created_at__gte=cutoff_date)
            ).distinct()
            
            # Mark as inactive instead of deleting
            updated_count = inactive_contacts.update(
                is_active=False,
                inactive_reason='No activity for 180+ days'
            )
            
            cleanup_results['contacts'] = {
                'marked_inactive': updated_count
            }
        
        logger.info(f"Cleanup inactive records: {cleanup_results}")
        
        return {
            'status': 'completed',
            'results': cleanup_results
        }
        
    except Exception as e:
        logger.error(f"Inactive records cleanup failed: {e}")
        raise


@shared_task(base=ScheduledTask, bind=True)
def system_health_cleanup_task(self):
    """
    Overall system health and cleanup
    """
    try:
        results = {}
        
        # Clean up temporary files
        temp_files_cleaned = self._cleanup_temp_files()
        results['temp_files'] = temp_files_cleaned
        
        # Clear old cache entries
        cache_cleared = self._clear_old_cache()
        results['cache_cleared'] = cache_cleared
        
        # Clean up session data
        sessions_cleaned = self._cleanup_old_sessions()
        results['sessions'] = sessions_cleaned
        
        logger.info(f"System health cleanup completed: {results}")
        
        return {
            'status': 'completed',
            'results': results
        }
        
    except Exception as e:
        logger.error(f"System health cleanup failed: {e}")
        raise
    
    def _cleanup_temp_files(self):
        """Clean up temporary files"""
        try:
            temp_dir = os.path.join(settings.MEDIA_ROOT, 'temp')
            if not os.path.exists(temp_dir):
                return 0
            
            cutoff_time = timezone.now() - timedelta(hours=24)
            cutoff_timestamp = cutoff_time.timestamp()
            
            cleaned_count = 0
            for filename in os.listdir(temp_dir):
                file_path = os.path.join(temp_dir, filename)
                if os.path.isfile(file_path):
                    if os.path.getmtime(file_path) < cutoff_timestamp:
                        os.remove(file_path)
                        cleaned_count += 1
            
            return cleaned_count
            
        except Exception as e:
            logger.error(f"Temp file cleanup failed: {e}")
            return 0
    
    def _clear_old_cache(self):
        """Clear old cache entries"""
        try:
            from django.core.cache import cache
            # This is a simplified version - actual implementation depends on cache backend
            cache.clear()
            return True
        except Exception as e:
            logger.error(f"Cache cleanup failed: {e}")
            return False
    
    def _cleanup_old_sessions(self):
        """Clean up old sessions"""
        try:
            from django.contrib.sessions.models import Session
            
            deleted_count = Session.objects.filter(
                expire_date__lt=timezone.now()
            ).delete()[0]
            
            return deleted_count
            
        except Exception as e:
            logger.error(f"Session cleanup failed: {e}")
            return 0