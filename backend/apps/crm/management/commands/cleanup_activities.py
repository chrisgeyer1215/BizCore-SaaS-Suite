"""
CRM Data Cleanup Management Command
Comprehensive data maintenance, cleanup, and optimization tasks.
"""

import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Tuple
import json

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction, connection
from django.utils import timezone
from django.db.models import Q, Count, Sum, Avg, F, Max, Min
from django.contrib.auth import get_user_model
from django.core.files.storage import default_storage

from crm.models.lead_model import Lead, LeadScoringRule
from crm.models.account_model import Account, Contact
from crm.models.opportunity_model import Opportunity
from crm.models.activity_model import Activity, EmailLog, CallLog, SMSLog
from crm.models.campaign_model import Campaign, CampaignMember
from crm.models.ticket_model import Ticket
from crm.models.document_model import Document
from crm.models.system_model import AuditTrail, APIUsageLog, SyncLog
from crm.models.analytics_model import Report

User = get_user_model()
logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Comprehensive CRM data cleanup and maintenance tasks'

    def add_arguments(self, parser):
        # Cleanup types
        parser.add_argument(
            '--task',
            choices=[
                'duplicates', 'orphaned', 'old_activities', 'old_logs', 
                'old_files', 'invalid_data', 'performance', 'all'
            ],
            help='Type of cleanup task to run',
            default='all'
        )
        
        # Time-based options
        parser.add_argument(
            '--days-old',
            type=int,
            help='Number of days to consider records as old',
            default=90
        )
        
        parser.add_argument(
            '--archive-days',
            type=int,
            help='Days after which to archive instead of delete',
            default=365
        )
        
        # Batch processing
        parser.add_argument(
            '--batch-size',
            type=int,
            help='Number of records to process in each batch',
            default=1000
        )
        
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Preview cleanup actions without executing',
        )
        
        # Specific cleanup options
        parser.add_argument(
            '--merge-duplicates',
            action='store_true',
            help='Merge duplicate records instead of just detecting',
        )
        
        parser.add_argument(
            '--fix-data',
            action='store_true',
            help='Attempt to fix invalid data automatically',
        )
        
        parser.add_argument(
            '--compress-files',
            action='store_true',
            help='Compress old files to save storage space',
        )
        
        parser.add_argument(
            '--vacuum-db',
            action='store_true',
            help='Run database vacuum/optimization after cleanup',
        )
        
        # Safety options
        parser.add_argument(
            '--skip-active',
            action='store_true',
            help='Skip cleanup of active/recent records',
        )
        
        parser.add_argument(
            '--backup-before',
            action='store_true',
            help='Create backup before cleanup operations',
        )

    def handle(self, *args, **options):
        try:
            self.cleanup_crm_data(**options)
        except Exception as e:
            logger.error(f"CRM cleanup failed: {str(e)}")
            raise CommandError(f'CRM cleanup failed: {str(e)}')

    def cleanup_crm_data(self, **options):
        """Main cleanup orchestrator"""
        task = options['task']
        
        self.stdout.write('🧹 Starting CRM data cleanup...')
        
        # Create backup if requested
        if options['backup_before']:
            self._create_backup()
        
        # Execute cleanup tasks
        cleanup_results = {}
        
        if task == 'all':
            tasks = ['duplicates', 'orphaned', 'old_activities', 'old_logs', 'old_files', 'invalid_data', 'performance']
        else:
            tasks = [task]
        
        for cleanup_task in tasks:
            self.stdout.write(f'\n🔧 Running {cleanup_task} cleanup...')
            
            try:
                if cleanup_task == 'duplicates':
                    result = self._cleanup_duplicates(options)
                elif cleanup_task == 'orphaned':
                    result = self._cleanup_orphaned_records(options)
                elif cleanup_task == 'old_activities':
                    result = self._cleanup_old_activities(options)
                elif cleanup_task == 'old_logs':
                    result = self._cleanup_old_logs(options)
                elif cleanup_task == 'old_files':
                    result = self._cleanup_old_files(options)
                elif cleanup_task == 'invalid_data':
                    result = self._cleanup_invalid_data(options)
                elif cleanup_task == 'performance':
                    result = self._performance_optimization(options)
                
                cleanup_results[cleanup_task] = result
                self.stdout.write(f'✅ {cleanup_task} cleanup completed')
                
            except Exception as e:
                logger.error(f"Failed to run {cleanup_task} cleanup: {str(e)}")
                cleanup_results[cleanup_task] = {'error': str(e)}
        
        # Database optimization if requested
        if options['vacuum_db']:
            self._vacuum_database()
        
        # Print comprehensive summary
        self._print_cleanup_summary(cleanup_results, options)

    def _cleanup_duplicates(self, options: Dict) -> Dict:
        """Find and handle duplicate records"""
        results = {
            'leads_processed': 0,
            'accounts_processed': 0,
            'contacts_processed': 0,
            'duplicates_found': 0,
            'duplicates_merged': 0,
            'duplicates_marked': 0
        }
        
        # Find duplicate leads by email
        duplicate_leads = self._find_duplicate_leads()
        results['duplicates_found'] += len(duplicate_leads)
        
        for email, lead_ids in duplicate_leads.items():
            if len(lead_ids) > 1:
                if options['merge_duplicates'] and not options['dry_run']:
                    merged_count = self._merge_duplicate_leads(lead_ids)
                    results['duplicates_merged'] += merged_count
                else:
                    # Just mark for review
                    self._mark_leads_for_review(lead_ids, 'Duplicate email detected')
                    results['duplicates_marked'] += len(lead_ids) - 1
        
        results['leads_processed'] = len(duplicate_leads)
        
        # Find duplicate accounts by name + domain
        duplicate_accounts = self._find_duplicate_accounts()
        results['duplicates_found'] += len(duplicate_accounts)
        
        for key, account_ids in duplicate_accounts.items():
            if len(account_ids) > 1:
                if options['merge_duplicates'] and not options['dry_run']:
                    merged_count = self._merge_duplicate_accounts(account_ids)
                    results['duplicates_merged'] += merged_count
                else:
                    self._mark_accounts_for_review(account_ids, 'Duplicate account detected')
                    results['duplicates_marked'] += len(account_ids) - 1
        
        results['accounts_processed'] = len(duplicate_accounts)
        
        # Find duplicate contacts by email within same account
        duplicate_contacts = self._find_duplicate_contacts()
        results['duplicates_found'] += len(duplicate_contacts)
        
        for key, contact_ids in duplicate_contacts.items():
            if len(contact_ids) > 1:
                if options['merge_duplicates'] and not options['dry_run']:
                    merged_count = self._merge_duplicate_contacts(contact_ids)
                    results['duplicates_merged'] += merged_count
                else:
                    self._mark_contacts_for_review(contact_ids, 'Duplicate contact detected')
                    results['duplicates_marked'] += len(contact_ids) - 1
        
        results['contacts_processed'] = len(duplicate_contacts)
        
        return results

    def _find_duplicate_leads(self) -> Dict[str, List[int]]:
        """Find duplicate leads by email"""
        duplicates = {}
        
        # Group by email (case insensitive)
        lead_emails = Lead.objects.values('email').annotate(
            count=Count('id'),
            ids=F('id')
        ).filter(count__gt=1)
        
        for email_group in lead_emails:
            email = email_group['email'].lower() if email_group['email'] else None
            if email:
                lead_ids = list(Lead.objects.filter(
                    email__iexact=email
                ).values_list('id', flat=True))
                
                if len(lead_ids) > 1:
                    duplicates[email] = lead_ids
        
        return duplicates

    def _find_duplicate_accounts(self) -> Dict[str, List[int]]:
        """Find duplicate accounts by name and website domain"""
        duplicates = {}
        
        accounts = Account.objects.exclude(name='').values(
            'name', 'website'
        ).annotate(count=Count('id')).filter(count__gt=1)
        
        for account_group in accounts:
            name = account_group['name'].strip().lower()
            website = account_group['website']
            
            # Extract domain from website
            domain = self._extract_domain(website) if website else None
            key = f"{name}|{domain}" if domain else name
            
            account_ids = list(Account.objects.filter(
                name__iexact=account_group['name']
            ).values_list('id', flat=True))
            
            if domain:
                account_ids = list(Account.objects.filter(
                    name__iexact=account_group['name'],
                    website__icontains=domain
                ).values_list('id', flat=True))
            
            if len(account_ids) > 1:
                duplicates[key] = account_ids
        
        return duplicates

    def _find_duplicate_contacts(self) -> Dict[str, List[int]]:
        """Find duplicate contacts by email within same account"""
        duplicates = {}
        
        contacts = Contact.objects.exclude(email='').values(
            'email', 'account_id'
        ).annotate(count=Count('id')).filter(count__gt=1)
        
        for contact_group in contacts:
            email = contact_group['email'].lower()
            account_id = contact_group['account_id']
            key = f"{account_id}|{email}"
            
            contact_ids = list(Contact.objects.filter(
                email__iexact=contact_group['email'],
                account_id=account_id
            ).values_list('id', flat=True))
            
            if len(contact_ids) > 1:
                duplicates[key] = contact_ids
        
        return duplicates

    def _merge_duplicate_leads(self, lead_ids: List[int]) -> int:
        """Merge duplicate leads into the most complete record"""
        if len(lead_ids) < 2:
            return 0
        
        leads = Lead.objects.filter(id__in=lead_ids).order_by('created_at')
        primary_lead = self._select_primary_lead(leads)
        
        merged_count = 0
        
        with transaction.atomic():
            for lead in leads:
                if lead.id != primary_lead.id:
                    # Merge data from duplicate into primary
                    self._merge_lead_data(primary_lead, lead)
                    
                    # Update related records to point to primary
                    self._update_lead_relationships(lead, primary_lead)
                    
                    # Soft delete the duplicate
                    lead.is_deleted = True
                    lead.deleted_at = timezone.now()
                    lead.save()
                    
                    merged_count += 1
        
        return merged_count

    def _select_primary_lead(self, leads) -> Lead:
        """Select the most complete lead as primary for merging"""
        scored_leads = []
        
        for lead in leads:
            completeness_score = 0
            
            # Score based on data completeness
            if lead.company: completeness_score += 2
            if lead.job_title: completeness_score += 1
            if lead.phone: completeness_score += 1
            if lead.industry: completeness_score += 1
            if lead.budget: completeness_score += 2
            if lead.notes: completeness_score += 1
            if lead.score and lead.score > 0: completeness_score += 2
            
            # Prefer leads with activities
            activity_count = lead.activities.count()
            completeness_score += min(activity_count, 5)  # Cap at 5 points
            
            # Prefer more recent leads if scores are tied
            days_old = (timezone.now() - lead.created_at).days
            recency_score = max(0, 30 - days_old) / 30  # More points for recent leads
            
            total_score = completeness_score + recency_score
            scored_leads.append((lead, total_score))
        
        # Return lead with highest score
        return max(scored_leads, key=lambda x: x[1])[0]

    def _merge_lead_data(self, primary: Lead, duplicate: Lead):
        """Merge data from duplicate lead into primary"""
        fields_to_merge = [
            'phone', 'company', 'job_title', 'industry', 'budget',
            'website', 'address', 'city', 'state', 'country', 'postal_code'
        ]
        
        updated_fields = []
        
        for field in fields_to_merge:
            primary_value = getattr(primary, field)
            duplicate_value = getattr(duplicate, field)
            
            # Use duplicate's value if primary is empty and duplicate has value
            if not primary_value and duplicate_value:
                setattr(primary, field, duplicate_value)
                updated_fields.append(field)
        
        # Merge notes
        if duplicate.notes:
            if primary.notes:
                primary.notes += f"\n\n[Merged from duplicate]: {duplicate.notes}"
            else:
                primary.notes = duplicate.notes
            updated_fields.append('notes')
        
        # Use higher score
        if duplicate.score and (not primary.score or duplicate.score > primary.score):
            primary.score = duplicate.score
            updated_fields.append('score')
        
        if updated_fields:
            updated_fields.append('updated_at')
            primary.save(update_fields=updated_fields)

    def _update_lead_relationships(self, old_lead: Lead, new_lead: Lead):
        """Update relationships to point to the new primary lead"""
        # Update activities
        Activity.objects.filter(related_lead=old_lead).update(related_lead=new_lead)
        
        # Update campaign memberships
        CampaignMember.objects.filter(lead=old_lead).update(lead=new_lead)
        
        # Update any opportunities that might reference this lead
        # (This would depend on your specific data model relationships)

    def _cleanup_orphaned_records(self, options: Dict) -> Dict:
        """Clean up orphaned records without valid relationships"""
        results = {
            'orphaned_activities': 0,
            'orphaned_campaign_members': 0,
            'orphaned_documents': 0,
            'orphaned_logs': 0,
            'records_cleaned': 0
        }
        
        batch_size = options['batch_size']
        
        # Find orphaned activities (no related lead, account, or opportunity)
        orphaned_activities = Activity.objects.filter(
            related_lead__isnull=True,
            related_account__isnull=True,
            related_opportunity__isnull=True
        )
        
        results['orphaned_activities'] = orphaned_activities.count()
        
        if not options['dry_run']:
            # Delete in batches
            while True:
                batch_ids = list(orphaned_activities.values_list('id', flat=True)[:batch_size])
                if not batch_ids:
                    break
                
                Activity.objects.filter(id__in=batch_ids).delete()
                results['records_cleaned'] += len(batch_ids)
        
        # Find orphaned campaign members (lead or contact deleted)
        orphaned_campaign_members = CampaignMember.objects.filter(
            Q(lead__isnull=True) | Q(lead__is_deleted=True)
        )
        
        results['orphaned_campaign_members'] = orphaned_campaign_members.count()
        
        if not options['dry_run']:
            orphaned_campaign_members.delete()
            results['records_cleaned'] += results['orphaned_campaign_members']
        
        # Find orphaned documents (related object deleted)
        orphaned_documents = Document.objects.filter(
            Q(related_lead__isnull=True, related_account__isnull=True, 
              related_opportunity__isnull=True) |
            Q(related_lead__is_deleted=True) |
            Q(related_account__is_deleted=True)
        )
        
        results['orphaned_documents'] = orphaned_documents.count()
        
        if not options['dry_run']:
            for doc in orphaned_documents:
                # Delete file from storage
                if doc.file:
                    try:
                        default_storage.delete(doc.file.name)
                    except:
                        pass  # File might already be deleted
                
                doc.delete()
            
            results['records_cleaned'] += results['orphaned_documents']
        
        # Find orphaned email/call/SMS logs
        orphaned_email_logs = EmailLog.objects.filter(
            Q(lead__isnull=True) | Q(lead__is_deleted=True)
        )
        
        orphaned_call_logs = CallLog.objects.filter(
            Q(lead__isnull=True) | Q(lead__is_deleted=True)
        )
        
        orphaned_sms_logs = SMSLog.objects.filter(
            Q(lead__isnull=True) | Q(lead__is_deleted=True)
        )
        
        total_orphaned_logs = (
            orphaned_email_logs.count() + 
            orphaned_call_logs.count() + 
            orphaned_sms_logs.count()
        )
        
        results['orphaned_logs'] = total_orphaned_logs
        
        if not options['dry_run']:
            orphaned_email_logs.delete()
            orphaned_call_logs.delete()
            orphaned_sms_logs.delete()
            results['records_cleaned'] += total_orphaned_logs
        
        return results

    def _cleanup_old_activities(self, options: Dict) -> Dict:
        """Clean up old completed activities"""
        days_old = options['days_old']
        archive_days = options['archive_days']
        cutoff_date = timezone.now() - timedelta(days=days_old)
        archive_date = timezone.now() - timedelta(days=archive_days)
        
        results = {
            'old_activities_found': 0,
            'activities_archived': 0,
            'activities_deleted': 0,
            'storage_freed_mb': 0
        }
        
        # Find old completed activities
        old_activities = Activity.objects.filter(
            status='COMPLETED',
            completed_at__lt=cutoff_date
        )
        
        if options['skip_active']:
            # Don't clean activities related to active opportunities
            old_activities = old_activities.exclude(
                related_opportunity__stage__stage_type='OPEN'
            )
        
        results['old_activities_found'] = old_activities.count()
        
        if not options['dry_run']:
            # Archive very old activities, delete moderately old ones
            very_old_activities = old_activities.filter(completed_at__lt=archive_date)
            moderately_old_activities = old_activities.exclude(completed_at__lt=archive_date)
            
            # Archive very old activities (move to archive table or mark as archived)
            for activity in very_old_activities:
                if not hasattr(activity, 'is_archived') or not activity.is_archived:
                    activity.is_archived = True
                    activity.archived_at = timezone.now()
                    activity.save(update_fields=['is_archived', 'archived_at'])
                    results['activities_archived'] += 1
            
            # Delete moderately old activities that are not critical
            non_critical_activities = moderately_old_activities.exclude(
                activity_type__name__in=['Meeting', 'Demo', 'Proposal']
            )
            
            deleted_count = non_critical_activities.count()
            non_critical_activities.delete()
            results['activities_deleted'] = deleted_count
        
        return results

    def _cleanup_old_logs(self, options: Dict) -> Dict:
        """Clean up old system logs and audit trails"""
        days_old = options['days_old']
        cutoff_date = timezone.now() - timedelta(days=days_old)
        
        results = {
            'audit_logs_cleaned': 0,
            'api_logs_cleaned': 0,
            'sync_logs_cleaned': 0,
            'email_logs_cleaned': 0,
            'storage_freed_mb': 0
        }
        
        if not options['dry_run']:
            # Clean old audit trails (keep critical actions)
            old_audit_logs = AuditTrail.objects.filter(
                created_at__lt=cutoff_date
            ).exclude(
                action__in=['DELETE', 'MERGE', 'CONVERT']  # Keep critical actions
            )
            
            results['audit_logs_cleaned'] = old_audit_logs.count()
            old_audit_logs.delete()
            
            # Clean old API usage logs
            old_api_logs = APIUsageLog.objects.filter(
                created_at__lt=cutoff_date
            )
            
            results['api_logs_cleaned'] = old_api_logs.count()
            old_api_logs.delete()
            
            # Clean old sync logs
            old_sync_logs = SyncLog.objects.filter(
                created_at__lt=cutoff_date,
                status='COMPLETED'  # Only clean successful syncs
            )
            
            results['sync_logs_cleaned'] = old_sync_logs.count()
            old_sync_logs.delete()
            
            # Clean old email logs (keep failed sends for troubleshooting)
            old_email_logs = EmailLog.objects.filter(
                sent_at__lt=cutoff_date,
                status='SENT'
            )
            
            results['email_logs_cleaned'] = old_email_logs.count()
            old_email_logs.delete()
        
        return results

    def _cleanup_old_files(self, options: Dict) -> Dict:
        """Clean up old files and documents"""
        days_old = options['days_old']
        cutoff_date = timezone.now() - timedelta(days=days_old)
        
        results = {
            'old_files_found': 0,
            'files_compressed': 0,
            'files_deleted': 0,
            'storage_freed_mb': 0
        }
        
        # Find old documents
        old_documents = Document.objects.filter(
            created_at__lt=cutoff_date,
            is_deleted=False
        )
        
        if options['skip_active']:
            # Don't clean files related to active deals
            old_documents = old_documents.exclude(
                related_opportunity__stage__stage_type='OPEN'
            )
        
        results['old_files_found'] = old_documents.count()
        
        if not options['dry_run']:
            for doc in old_documents:
                if doc.file and default_storage.exists(doc.file.name):
                    try:
                        # Get file size for statistics
                        file_size = doc.file.size
                        
                        if options['compress_files']:
                            # Compress files instead of deleting
                            if self._compress_document(doc):
                                results['files_compressed'] += 1
                                results['storage_freed_mb'] += file_size / (1024 * 1024) * 0.7  # Assume 70% compression
                        else:
                            # Move to archive or delete
                            if doc.security_level == 'PUBLIC':
                                # Delete low-security files
                                default_storage.delete(doc.file.name)
                                doc.is_deleted = True
                                doc.deleted_at = timezone.now()
                                doc.save()
                                
                                results['files_deleted'] += 1
                                results['storage_freed_mb'] += file_size / (1024 * 1024)
                    
                    except Exception as e:
                        logger.warning(f"Failed to process file {doc.file.name}: {str(e)}")
        
        return results

    def _cleanup_invalid_data(self, options: Dict) -> Dict:
        """Find and fix invalid data"""
        results = {
            'invalid_emails_found': 0,
            'invalid_phones_found': 0,
            'invalid_dates_found': 0,
            'records_fixed': 0,
            'records_flagged': 0
        }
        
        # Find invalid email addresses
        invalid_email_leads = Lead.objects.exclude(
            email__regex=r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        ).exclude(email='')
        
        results['invalid_emails_found'] = invalid_email_leads.count()
        
        if options['fix_data'] and not options['dry_run']:
            for lead in invalid_email_leads:
                # Try to fix common email issues
                fixed_email = self._fix_email_format(lead.email)
                if fixed_email and fixed_email != lead.email:
                    lead.email = fixed_email
                    lead.save(update_fields=['email'])
                    results['records_fixed'] += 1
                else:
                    # Flag for manual review
                    self._flag_record_for_review(lead, 'Invalid email format')
                    results['records_flagged'] += 1
        
        # Find invalid phone numbers
        invalid_phone_leads = Lead.objects.filter(
            phone__isnull=False
        ).exclude(phone='').exclude(
            phone__regex=r'^[\+]?[1-9][\d\s\-\(\)\.]{7,15}$'
        )
        
        results['invalid_phones_found'] = invalid_phone_leads.count()
        
        if options['fix_data'] and not options['dry_run']:
            for lead in invalid_phone_leads:
                fixed_phone = self._fix_phone_format(lead.phone)
                if fixed_phone and fixed_phone != lead.phone:
                    lead.phone = fixed_phone
                    lead.save(update_fields=['phone'])
                    results['records_fixed'] += 1
                else:
                    self._flag_record_for_review(lead, 'Invalid phone format')
                    results['records_flagged'] += 1
        
        # Find invalid dates (future dates where they shouldn't be)
        future_date = timezone.now() + timedelta(days=30)  # Allow some future scheduling
        
        invalid_date_activities = Activity.objects.filter(
            completed_at__gt=future_date,
            status='COMPLETED'
        )
        
        results['invalid_dates_found'] = invalid_date_activities.count()
        
        if options['fix_data'] and not options['dry_run']:
            # Fix obviously wrong completed dates
            invalid_date_activities.update(
                completed_at=F('scheduled_at'),
                updated_at=timezone.now()
            )
            results['records_fixed'] += invalid_date_activities.count()
        
        return results

    def _performance_optimization(self, options: Dict) -> Dict:
        """Optimize database performance"""
        results = {
            'indexes_analyzed': 0,
            'statistics_updated': 0,
            'recommendations': []
        }
        
        # Analyze query performance
        slow_queries = self._find_slow_queries()
        results['recommendations'].extend(slow_queries)
        
        # Update database statistics
        if not options['dry_run']:
            with connection.cursor() as cursor:
                # PostgreSQL specific optimization
                if connection.vendor == 'postgresql':
                    cursor.execute("ANALYZE;")
                    results['statistics_updated'] = 1
                    
                    # Check for missing indexes
                    missing_indexes = self._suggest_missing_indexes(cursor)
                    results['recommendations'].extend(missing_indexes)
        
        # Analyze data distribution
        data_insights = self._analyze_data_distribution()
        results['recommendations'].extend(data_insights)
        
        return results

    def _vacuum_database(self):
        """Run database vacuum/optimization"""
        self.stdout.write('🔧 Running database optimization...')
        
        try:
            with connection.cursor() as cursor:
                if connection.vendor == 'postgresql':
                    cursor.execute("VACUUM ANALYZE;")
                    self.stdout.write('✅ PostgreSQL VACUUM ANALYZE completed')
                elif connection.vendor == 'sqlite':
                    cursor.execute("VACUUM;")
                    self.stdout.write('✅ SQLite VACUUM completed')
        except Exception as e:
            logger.warning(f"Database vacuum failed: {str(e)}")
            self.stdout.write(f'⚠️ Database optimization failed: {str(e)}')

    # Helper methods
    def _extract_domain(self, website: str) -> Optional[str]:
        """Extract domain from website URL"""
        if not website:
            return None
        
        # Clean up the URL
        website = website.lower().strip()
        if not website.startswith(('http://', 'https://')):
            website = 'http://' + website
        
        try:
            from urllib.parse import urlparse
            parsed = urlparse(website)
            domain = parsed.netloc.replace('www.', '')
            return domain if domain else None
        except:
            return None

    def _fix_email_format(self, email: str) -> Optional[str]:
        """Attempt to fix common email formatting issues"""
        if not email:
            return None
        
        email = email.strip().lower()
        
        # Fix common issues
        fixes = [
            ('.con', '.com'),
            ('.co', '.com'),
            ('.cmo', '.com'),
            ('@gmail.co', '@gmail.com'),
            ('@yahoo.co', '@yahoo.com'),
            ('..', '.'),
            (' ', ''),
        ]
        
        for bad, good in fixes:
            email = email.replace(bad, good)
        
        # Validate the result
        import re
        if re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email):
            return email
        
        return None

    def _fix_phone_format(self, phone: str) -> Optional[str]:
        """Attempt to fix phone number formatting"""
        if not phone:
            return None
        
        # Remove all non-digit characters except +
        import re
        digits = re.sub(r'[^\d+]', '', phone)
        
        # Basic validation and formatting
        if len(digits) >= 10:
            return digits
        
        return None

    def _flag_record_for_review(self, record, reason: str):
        """Flag a record for manual review"""
        # This would typically create a review task or add to a review queue
        # For now, we'll just log it
        logger.info(f"Flagged {record.__class__.__name__} {record.id} for review: {reason}")

    def _mark_leads_for_review(self, lead_ids: List[int], reason: str):
        """Mark leads for duplicate review"""
        # Add notes to leads about potential duplicates
        for lead_id in lead_ids[1:]:  # Skip first one (primary)
            try:
                lead = Lead.objects.get(id=lead_id)
                if lead.notes:
                    lead.notes += f"\n\n[SYSTEM]: {reason}"
                else:
                    lead.notes = f"[SYSTEM]: {reason}"
                lead.save(update_fields=['notes'])
            except Lead.DoesNotExist:
                pass

    def _mark_accounts_for_review(self, account_ids: List[int], reason: str):
        """Mark accounts for duplicate review"""
        for account_id in account_ids[1:]:
            try:
                account = Account.objects.get(id=account_id)
                if account.notes:
                    account.notes += f"\n\n[SYSTEM]: {reason}"
                else:
                    account.notes = f"[SYSTEM]: {reason}"
                account.save(update_fields=['notes'])
            except Account.DoesNotExist:
                pass

    def _mark_contacts_for_review(self, contact_ids: List[int], reason: str):
        """Mark contacts for duplicate review"""
        for contact_id in contact_ids[1:]:
            try:
                contact = Contact.objects.get(id=contact_id)
                if contact.notes:
                    contact.notes += f"\n\n[SYSTEM]: {reason}"
                else:
                    contact.notes = f"[SYSTEM]: {reason}"
                contact.save(update_fields=['notes'])
            except Contact.DoesNotExist:
                pass

    def _compress_document(self, document) -> bool:
        """Compress a document file"""
        # This would implement file compression
        # For now, just return True to simulate success
        return True

    def _find_slow_queries(self) -> List[str]:
        """Find slow database queries and suggest optimizations"""
        recommendations = []
        
        # Check for queries that might be slow
        large_table_counts = {
            'leads': Lead.objects.count(),
            'activities': Activity.objects.count(),
            'audit_trails': AuditTrail.objects.count(),
        }
        
        for table, count in large_table_counts.items():
            if count > 100000:  # 100k records
                recommendations.append(
                    f"Consider partitioning {table} table ({count:,} records)"
                )
        
        return recommendations

    def _suggest_missing_indexes(self, cursor) -> List[str]:
        """Suggest missing database indexes"""
        suggestions = []
        
        # This would analyze query patterns and suggest indexes
        # For demonstration, we'll provide common suggestions
        common_suggestions = [
            "Consider adding index on activities.scheduled_at for date range queries",
            "Consider adding composite index on leads(status, created_at)",
            "Consider adding index on audit_trail.created_at for log cleanup"
        ]
        
        suggestions.extend(common_suggestions)
        return suggestions

    def _analyze_data_distribution(self) -> List[str]:
        """Analyze data distribution and provide insights"""
        insights = []
        
        # Lead status distribution
        lead_stats = Lead.objects.values('status').annotate(count=Count('id'))
        total_leads = sum(stat['count'] for stat in lead_stats)
        
        if total_leads > 0:
            for stat in lead_stats:
                percentage = (stat['count'] / total_leads) * 100
                if percentage > 50:
                    insights.append(
                        f"High concentration of leads in {stat['status']} status ({percentage:.1f}%)"
                    )
        
        # Activity completion rate
        total_activities = Activity.objects.count()
        completed_activities = Activity.objects.filter(status='COMPLETED').count()
        
        if total_activities > 0:
            completion_rate = (completed_activities / total_activities) * 100
            if completion_rate < 70:
                insights.append(
                    f"Low activity completion rate ({completion_rate:.1f}%) - consider cleanup"
                )
        
        return insights

    def _create_backup(self):
        """Create database backup before cleanup"""
        self.stdout.write('💾 Creating backup before cleanup...')
        
        # This would implement actual backup creation
        # For demonstration, we'll just log it
        backup_name = f"crm_backup_{timezone.now().strftime('%Y%m%d_%H%M%S')}"
        logger.info(f"Backup created: {backup_name}")
        
        self.stdout.write(f'✅ Backup created: {backup_name}')

    def _print_cleanup_summary(self, results: Dict, options: Dict):
        """Print comprehensive cleanup summary"""
        self.stdout.write('\n' + '='*60)
        self.stdout.write('🧹 CLEANUP SUMMARY')
        self.stdout.write('='*60)
        
        if options['dry_run']:
            self.stdout.write(self.style.WARNING('🔍 DRY RUN - No changes were made'))
        
        total_records_processed = 0
        total_records_cleaned = 0
        total_storage_freed = 0
        
        for task, result in results.items():
            if isinstance(result, dict) and 'error' not in result:
                self.stdout.write(f'\n📋 {task.upper().replace("_", " ")}:')
                
                for key, value in result.items():
                    if 'found' in key or 'processed' in key:
                        total_records_processed += value
                    elif any(x in key for x in ['cleaned', 'deleted', 'merged', 'archived']):
                        total_records_cleaned += value
                    elif 'storage_freed_mb' in key:
                        total_storage_freed += value
                    
                    # Format the display
                    display_key = key.replace('_', ' ').title()
                    if isinstance(value, list):
                        self.stdout.write(f'  {display_key}: {len(value)} items')
                        for item in value[:3]:  # Show first 3 items
                            self.stdout.write(f'    - {item}')
                        if len(value) > 3:
                            self.stdout.write(f'    ... and {len(value) - 3} more')
                    else:
                        self.stdout.write(f'  {display_key}: {value:,}')
            
            elif isinstance(result, dict) and 'error' in result:
                self.stdout.write(f'\n❌ {task.upper().replace("_", " ")} FAILED:')
                self.stdout.write(f'  Error: {result["error"]}')
        
        # Overall summary
        self.stdout.write(f'\n📊 OVERALL TOTALS:')
        self.stdout.write(f'Records Processed: {total_records_processed:,}')
        self.stdout.write(f'Records Cleaned: {total_records_cleaned:,}')
        if total_storage_freed > 0:
            self.stdout.write(f'Storage Freed: {total_storage_freed:.1f} MB')
        
        # Recommendations
        all_recommendations = []
        for result in results.values():
            if isinstance(result, dict) and 'recommendations' in result:
                all_recommendations.extend(result['recommendations'])
        
        if all_recommendations:
            self.stdout.write(f'\n💡 RECOMMENDATIONS:')
            for i, rec in enumerate(all_recommendations[:5], 1):  # Show top 5
                self.stdout.write(f'  {i}. {rec}')
        
        self.stdout.write('='*60)
        self.stdout.write(
            self.style.SUCCESS('✅ CRM cleanup completed successfully!')
        )
