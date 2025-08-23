"""
Document Manager - Document Management System
Advanced file management, versioning, and sharing
"""

from django.db.models import Q, Count, Sum, Avg, Max, Min, Case, When, F
from django.utils import timezone
from datetime import timedelta
from django.core.files.storage import default_storage
import os
import mimetypes
from .base import AnalyticsManager


class DocumentManager(AnalyticsManager):
    """
    Advanced Document Manager
    File management with versioning and sharing capabilities
    """
    
    def active_documents(self):
        """Get active (non-deleted) documents"""
        return self.filter(is_deleted=False)
    
    def by_category(self, category):
        """Filter documents by category"""
        return self.filter(category=category)
    
    def by_entity(self, entity_type, entity_id):
        """Get documents for specific entity"""
        return self.filter(
            entity_type=entity_type,
            entity_id=entity_id
        )
    
    def by_file_type(self, file_type):
        """Filter documents by file type/extension"""
        return self.filter(file_type__iexact=file_type)
    
    def uploaded_by_user(self, user):
        """Get documents uploaded by specific user"""
        return self.filter(uploaded_by=user)
    
    def shared_documents(self):
        """Get documents that have been shared"""
        return self.filter(shares__isnull=False).distinct()
    
    def public_documents(self):
        """Get publicly accessible documents"""
        return self.filter(is_public=True)
    
    def recent_documents(self, days=7):
        """Get recently uploaded documents"""
        cutoff_date = timezone.now() - timedelta(days=days)
        return self.filter(uploaded_at__gte=cutoff_date)
    
    def large_files(self, size_mb=10):
        """Get files larger than specified size (in MB)"""
        size_bytes = size_mb * 1024 * 1024
        return self.filter(file_size__gte=size_bytes)
    
    def get_storage_analytics(self, tenant):
        """Get comprehensive storage analytics"""
        return self.for_tenant(tenant).aggregate(
            # Count metrics
            total_documents=Count('id'),
            active_documents=Count('id', filter=Q(is_deleted=False)),
            shared_documents=Count('id', filter=Q(shares__isnull=False), distinct=True),
            public_documents=Count('id', filter=Q(is_public=True)),
            
            # Size metrics
            total_storage_used=Sum('file_size'),
            avg_file_size=Avg('file_size'),
            largest_file=Max('file_size'),
            smallest_file=Min('file_size'),
            
            # Activity metrics
            documents_uploaded_today=Count('id', filter=Q(
                uploaded_at__date=timezone.now().date()
            )),
            documents_uploaded_this_week=Count('id', filter=Q(
                uploaded_at__gte=timezone.now() - timedelta(days=7)
            )),
            documents_uploaded_this_month=Count('id', filter=Q(
                uploaded_at__gte=timezone.now() - timedelta(days=30)
            )),
            
            # Download metrics
            total_downloads=Sum('download_count'),
            avg_downloads_per_document=Avg('download_count'),
            most_downloaded_count=Max('download_count')
        )
    
    def get_file_type_distribution(self, tenant):
        """Get distribution of file types"""
        return self.for_tenant(tenant).values('file_type').annotate(
            count=Count('id'),
            total_size=Sum('file_size'),
            avg_size=Avg('file_size'),
            total_downloads=Sum('download_count')
        ).order_by('-count')
    
    def get_category_usage(self, tenant):
        """Analyze document usage by category"""
        return self.for_tenant(tenant).values(
            'category__name'
        ).annotate(
            document_count=Count('id'),
            total_size=Sum('file_size'),
            total_downloads=Sum('download_count'),
            avg_downloads=Avg('download_count'),
            recent_uploads=Count('id', filter=Q(
                uploaded_at__gte=timezone.now() - timedelta(days=30)
            ))
        ).order_by('-document_count')
    
    def get_sharing_analytics(self, tenant):
        """Analyze document sharing patterns"""
        from ..models import DocumentShare
        
        sharing_stats = self.for_tenant(tenant).aggregate(
            documents_with_shares=Count('id', filter=Q(shares__isnull=False), distinct=True),
            total_shares=Count('shares'),
            active_shares=Count('shares', filter=Q(
                shares__is_active=True,
                shares__expires_at__gt=timezone.now()
            )),
            expired_shares=Count('shares', filter=Q(
                shares__expires_at__lte=timezone.now()
            ))
        )
        
        # Most shared documents
        most_shared = self.for_tenant(tenant).annotate(
            share_count=Count('shares')
        ).filter(share_count__gt=0).order_by('-share_count')[:10]
        
        # Sharing by user
        sharing_by_user = DocumentShare.objects.filter(
            tenant=tenant,
            is_active=True
        ).values(
            'shared_by__first_name',
            'shared_by__last_name'
        ).annotate(
            shares_created=Count('id'),
            unique_documents_shared=Count('document', distinct=True)
        ).order_by('-shares_created')
        
        return {
            'sharing_stats': sharing_stats,
            'most_shared_documents': [
                {
                    'id': doc.id,
                    'name': doc.name,
                    'share_count': doc.share_count,
                    'file_type': doc.file_type
                }
                for doc in most_shared
            ],
            'sharing_by_user': list(sharing_by_user)
        }
    
    def get_access_analytics(self, tenant, days=30):
        """Analyze document access patterns"""
        end_date = timezone.now()
        start_date = end_date - timedelta(days=days)
        
        # Daily access patterns
        daily_access = self.for_tenant(tenant).filter(
            access_logs__accessed_at__range=[start_date, end_date]
        ).extra(
            select={'day': 'date(access_logs__accessed_at)'}
        ).values('day').annotate(
            unique_documents_accessed=Count('id', distinct=True),
            total_accesses=Count('access_logs'),
            unique_users=Count('access_logs__user', distinct=True)
        ).order_by('day')
        
        # Most accessed documents
        most_accessed = self.for_tenant(tenant).annotate(
            recent_access_count=Count('access_logs', filter=Q(
                access_logs__accessed_at__range=[start_date, end_date]
            ))
        ).filter(recent_access_count__gt=0).order_by('-recent_access_count')[:15]
        
        return {
            'daily_access_patterns': list(daily_access),
            'most_accessed_documents': [
                {
                    'id': doc.id,
                    'name': doc.name,
                    'access_count': doc.recent_access_count,
                    'file_type': doc.file_type,
                    'category': doc.category.name if doc.category else None
                }
                for doc in most_accessed
            ]
        }
    
    def get_version_analytics(self, tenant):
        """Analyze document versioning patterns"""
        versioned_docs = self.for_tenant(tenant).filter(
            version__gt=1
        )
        
        version_stats = versioned_docs.aggregate(
            total_versioned_documents=Count('id'),
            avg_versions_per_document=Avg('version'),
            max_versions=Max('version'),
            total_versions=Sum('version')
        )
        
        # Documents with most versions
        most_versioned = versioned_docs.order_by('-version')[:10]
        
        return {
            'version_stats': version_stats,
            'most_versioned_documents': [
                {
                    'id': doc.id,
                    'name': doc.name,
                    'version': doc.version,
                    'file_type': doc.file_type,
                    'last_modified': doc.modified_at
                }
                for doc in most_versioned
            ]
        }
    
    def cleanup_orphaned_files(self, tenant, dry_run=True):
        """Clean up files that exist in storage but not in database"""
        from django.conf import settings
        
        # Get all document file paths from database
        db_files = set(
            self.for_tenant(tenant).values_list('file', flat=True)
        )
        
        # Get all files in document storage directory
        document_storage_path = os.path.join(settings.MEDIA_ROOT, 'documents', str(tenant.id))
        orphaned_files = []
        total_size_saved = 0
        
        if os.path.exists(document_storage_path):
            for root, dirs, files in os.walk(document_storage_path):
                for file in files:
                    file_path = os.path.join(root, file)
                    relative_path = os.path.relpath(file_path, settings.MEDIA_ROOT)
                    
                    if relative_path not in db_files:
                        file_size = os.path.getsize(file_path)
                        orphaned_files.append({
                            'path': file_path,
                            'size': file_size,
                            'modified': os.path.getmtime(file_path)
                        })
                        total_size_saved += file_size
                        
                        if not dry_run:
                            try:
                                os.remove(file_path)
                            except OSError:
                                pass
        
        return {
            'orphaned_files_found': len(orphaned_files),
            'total_size_to_save': total_size_saved,
            'files_deleted': 0 if dry_run else len(orphaned_files),
            'dry_run': dry_run
        }
    
    def bulk_categorize_documents(self, tenant, categorization_rules):
        """
        Bulk categorize documents based on rules
        
        categorization_rules format:
        {
            'pdf': {'category_id': 1, 'tags': ['document']},
            'jpg': {'category_id': 2, 'tags': ['image']},
            'contract': {'category_id': 3, 'tags': ['legal', 'contract']}  # by filename
        }
        """
        categorized_count = 0
        
        for rule_key, rule_data in categorization_rules.items():
            # Rule by file extension
            if rule_key in ['pdf', 'doc', 'docx', 'jpg', 'png', 'xlsx', 'csv']:
                documents = self.for_tenant(tenant).filter(
                    file_type__iexact=rule_key,
                    category__isnull=True  # Only uncategorized
                )
            # Rule by filename pattern
            else:
                documents = self.for_tenant(tenant).filter(
                    name__icontains=rule_key,
                    category__isnull=True
                )
            
            # Update documents
            updated = documents.update(
                category_id=rule_data.get('category_id'),
                tags=', '.join(rule_data.get('tags', [])),
                modified_at=timezone.now()
            )
            categorized_count += updated
        
        return {
            'categorized_documents': categorized_count,
            'rules_applied': len(categorization_rules)
        }
    
    def generate_usage_report(self, tenant, days=30):
        """Generate comprehensive document usage report"""
        end_date = timezone.now()
        start_date = end_date - timedelta(days=days)
        
        # Overall usage metrics
        usage_metrics = self.get_storage_analytics(tenant)
        
        # Period-specific metrics
        period_metrics = self.for_tenant(tenant).filter(
            uploaded_at__range=[start_date, end_date]
        ).aggregate(
            new_documents=Count('id'),
            storage_added=Sum('file_size'),
            avg_file_size=Avg('file_size')
        )
        
        # Top uploaders
        top_uploaders = self.for_tenant(tenant).filter(
            uploaded_at__range=[start_date, end_date]
        ).values(
            'uploaded_by__first_name',
            'uploaded_by__last_name'
        ).annotate(
            documents_uploaded=Count('id'),
            storage_used=Sum('file_size')
        ).order_by('-documents_uploaded')[:10]
        
        # Usage by entity type
        entity_usage = self.for_tenant(tenant).values('entity_type').annotate(
            document_count=Count('id'),
            total_size=Sum('file_size')
        ).order_by('-document_count')
        
        return {
            'overall_metrics': usage_metrics,
            'period_metrics': period_metrics,
            'top_uploaders': list(top_uploaders),
            'usage_by_entity': list(entity_usage),
            'file_type_distribution': list(self.get_file_type_distribution(tenant)),
            'report_period': f"{start_date.date()} to {end_date.date()}"
        }
    
    def auto_tag_documents(self, tenant, tagging_rules):
        """
        Automatically tag documents based on content or metadata
        
        tagging_rules format:
        {
            'filename_patterns': {
                'invoice': ['billing', 'finance'],
                'contract': ['legal', 'agreement'],
                'proposal': ['sales', 'proposal']
            },
            'file_type_tags': {
                'pdf': ['document'],
                'jpg': ['image'],
                'xlsx': ['spreadsheet']
            }
        }
        """
        tagged_count = 0
        
        # Tag by filename patterns
        for pattern, tags in tagging_rules.get('filename_patterns', {}).items():
            documents = self.for_tenant(tenant).filter(
                name__icontains=pattern,
                tags__isnull=True
            )
            
            updated = documents.update(
                tags=', '.join(tags),
                modified_at=timezone.now()
            )
            tagged_count += updated
        
        # Tag by file type
        for file_type, tags in tagging_rules.get('file_type_tags', {}).items():
            documents = self.for_tenant(tenant).filter(
                file_type__iexact=file_type,
                tags__isnull=True
            )
            
            updated = documents.update(
                tags=', '.join(tags),
                modified_at=timezone.now()
            )
            tagged_count += updated
        
        return {
            'tagged_documents': tagged_count,
            'rules_applied': len(tagging_rules.get('filename_patterns', {})) + len(tagging_rules.get('file_type_tags', {}))
        }
    
    def identify_duplicate_documents(self, tenant):
        """Identify potentially duplicate documents"""
        # Simple duplicate detection based on filename and size
        duplicates = self.for_tenant(tenant).values(
            'name', 'file_size'
        ).annotate(
            count=Count('id'),
            ids=Count('id')  # We'll get the actual IDs in a separate query
        ).filter(count__gt=1).order_by('-count')
        
        duplicate_groups = []
        for duplicate in duplicates:
            duplicate_docs = self.for_tenant(tenant).filter(
                name=duplicate['name'],
                file_size=duplicate['file_size']
            ).values('id', 'name', 'uploaded_at', 'uploaded_by__first_name', 'version')
            
            duplicate_groups.append({
                'name': duplicate['name'],
                'file_size': duplicate['file_size'],
                'count': duplicate['count'],
                'documents': list(duplicate_docs)
            })
        
        return duplicate_groups
    
    def bulk_delete_old_versions(self, tenant, keep_versions=3, days_old=90):
        """Bulk delete old document versions"""
        cutoff_date = timezone.now() - timedelta(days=days_old)
        
        # Find documents with multiple versions
        versioned_docs = self.for_tenant(tenant).filter(
            version__gt=1,
            modified_at__lt=cutoff_date
        )
        
        deleted_count = 0
        space_saved = 0
        
        for doc in versioned_docs:
            # Get all versions of this document
            all_versions = self.for_tenant(tenant).filter(
                parent_document=doc.parent_document or doc
            ).order_by('-version')
            
            # Keep only the latest N versions
            versions_to_delete = all_versions[keep_versions:]
            
            for old_version in versions_to_delete:
                if old_version.file_size:
                    space_saved += old_version.file_size
                
                # Delete the physical file
                try:
                    if old_version.file:
                        default_storage.delete(old_version.file.name)
                except:
                    pass
                
                old_version.delete()
                deleted_count += 1
        
        return {
            'versions_deleted': deleted_count,
            'space_saved_bytes': space_saved,
            'space_saved_mb': round(space_saved / (1024 * 1024), 2)
        }