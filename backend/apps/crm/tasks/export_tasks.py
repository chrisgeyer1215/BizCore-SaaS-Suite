"""
Export Tasks
Handle data export, report generation, and file delivery
"""

from celery import shared_task
from django.utils import timezone
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.conf import settings
from django.template.loader import render_to_string
import logging
import pandas as pd
import io
import json
from datetime import timedelta
import os
import zipfile

from .base import TenantAwareTask, MonitoredTask, CacheAwareTask
from ..models import (
    Lead, Contact, Account, Opportunity, Activity, Product,
    ExportJob, Report, Campaign
)
from ..services.export_service import ExportService
from ..utils.tenant_utils import get_tenant_by_id

logger = logging.getLogger(__name__)


@shared_task(base=MonitoredTask, bind=True)
def export_data_task(self, tenant_id, export_config, export_job_id):
    """
    Export CRM data in various formats
    """
    try:
        tenant = get_tenant_by_id(tenant_id)
        service = ExportService(tenant=tenant)
        
        # Get export job
        export_job = ExportJob.objects.get(id=export_job_id, tenant=tenant)
        export_job.status = 'processing'
        export_job.started_at = timezone.now()
        export_job.save(update_fields=['status', 'started_at'])
        
        # Extract export parameters
        export_type = export_config.get('type', 'leads')
        export_format = export_config.get('format', 'csv')
        filters = export_config.get('filters', {})
        fields = export_config.get('fields', [])
        
        # Get data based on type
        if export_type == 'leads':
            data = service.export_leads(filters=filters, fields=fields)
        elif export_type == 'contacts':
            data = service.export_contacts(filters=filters, fields=fields)
        elif export_type == 'accounts':
            data = service.export_accounts(filters=filters, fields=fields)
        elif export_type == 'opportunities':
            data = service.export_opportunities(filters=filters, fields=fields)
        elif export_type == 'activities':
            data = service.export_activities(filters=filters, fields=fields)
        elif export_type == 'products':
            data = service.export_products(filters=filters, fields=fields)
        else:
            raise ValueError(f"Unsupported export type: {export_type}")
        
        # Generate file based on format
        if export_format == 'csv':
            file_content, filename = self._generate_csv_export(data, export_type)
        elif export_format == 'excel':
            file_content, filename = self._generate_excel_export(data, export_type)
        elif export_format == 'json':
            file_content, filename = self._generate_json_export(data, export_type)
        elif export_format == 'pdf':
            file_content, filename = self._generate_pdf_export(data, export_type, tenant)
        else:
            raise ValueError(f"Unsupported export format: {export_format}")
        
        # Save file
        file_path = f"exports/{tenant.id}/{filename}"
        saved_path = default_storage.save(file_path, ContentFile(file_content))
        
        # Generate download URL
        download_url = service.generate_download_url(saved_path)
        
        # Update export job
        export_job.status = 'completed'
        export_job.completed_at = timezone.now()
        export_job.file_path = saved_path
        export_job.download_url = download_url
        export_job.file_size = len(file_content)
        export_job.record_count = len(data) if isinstance(data, list) else data.count()
        export_job.expires_at = timezone.now() + timedelta(days=7)  # 7 days expiry
        export_job.save()
        
        # Send notification email if requested
        if export_config.get('notify_email'):
            from .email_tasks import send_email_task
            
            send_email_task.delay(
                recipient_email=export_job.created_by.email,
                subject=f"Export Ready: {export_type.title()} Data",
                message="",
                template_id='export_ready',
                context={
                    'user_name': export_job.created_by.get_full_name(),
                    'export_type': export_type.title(),
                    'record_count': export_job.record_count,
                    'download_url': f"{settings.FRONTEND_URL}/exports/{export_job.id}/download",
                    'expires_at': export_job.expires_at.strftime('%B %d, %Y')
                },
                tenant_id=tenant.id
            )
        
        logger.info(f"Export completed: {export_job.record_count} {export_type} records")
        
        return {
            'status': 'completed',
            'export_job_id': export_job.id,
            'download_url': download_url,
            'record_count': export_job.record_count,
            'file_size': export_job.file_size
        }
        
    except Exception as e:
        # Update export job with error
        try:
            export_job = ExportJob.objects.get(id=export_job_id)
            export_job.status = 'failed'
            export_job.error_message = str(e)
            export_job.completed_at = timezone.now()
            export_job.save()
        except:
            pass
        
        logger.error(f"Export task failed: {e}")
        raise
    
    def _generate_csv_export(self, data, export_type):
        """Generate CSV export"""
        if hasattr(data, 'to_csv'):
            # If data is a DataFrame
            csv_content = data.to_csv(index=False)
        else:
            # Convert queryset to DataFrame
            df = pd.DataFrame(list(data.values()))
            csv_content = df.to_csv(index=False)
        
        filename = f"{export_type}_{timezone.now().strftime('%Y%m%d_%H%M%S')}.csv"
        return csv_content.encode('utf-8'), filename
    
    def _generate_excel_export(self, data, export_type):
        """Generate Excel export"""
        buffer = io.BytesIO()
        
        if hasattr(data, 'to_excel'):
            data.to_excel(buffer, index=False, engine='openpyxl')
        else:
            df = pd.DataFrame(list(data.values()))
            df.to_excel(buffer, index=False, engine='openpyxl')
        
        filename = f"{export_type}_{timezone.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        return buffer.getvalue(), filename
    
    def _generate_json_export(self, data, export_type):
        """Generate JSON export"""
        if hasattr(data, 'values'):
            json_data = list(data.values())
        else:
            json_data = data
        
        json_content = json.dumps(json_data, indent=2, default=str)
        filename = f"{export_type}_{timezone.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        return json_content.encode('utf-8'), filename
    
    def _generate_pdf_export(self, data, export_type, tenant):
        """Generate PDF export"""
        try:
            from weasyprint import HTML, CSS
            from django.template.loader import render_to_string
            
            # Convert data for template
            if hasattr(data, 'values'):
                records = list(data.values())
            else:
                records = data
            
            # Render HTML template
            html_content = render_to_string(f'crm/exports/{export_type}_pdf.html', {
                'records': records[:1000],  # Limit to 1000 records for PDF
                'tenant': tenant,
                'export_date': timezone.now(),
                'record_count': len(records)
            })
            
            # Generate PDF
            html = HTML(string=html_content)
            pdf_content = html.write_pdf()
            
            filename = f"{export_type}_{timezone.now().strftime('%Y%m%d_%H%M%S')}.pdf"
            return pdf_content, filename
            
        except ImportError:
            # Fallback to CSV if WeasyPrint not available
            logger.warning("WeasyPrint not available, falling back to CSV")
            return self._generate_csv_export(data, export_type)


@shared_task(base=TenantAwareTask, bind=True)
def generate_report_task(self, tenant_id, report_id, report_params=None):
    """
    Generate custom report
    """
    try:
        tenant = get_tenant_by_id(tenant_id)
        report = Report.objects.get(id=report_id, tenant=tenant)
        service = ExportService(tenant=tenant)
        
        # Generate report data
        report_data = service.generate_report_data(
            report=report,
            params=report_params or {}
        )
        
        # Create export job for the report
        export_job = ExportJob.objects.create(
            tenant=tenant,
            export_type='report',
            report=report,
            created_by=report.created_by,
            config={
                'report_id': report.id,
                'params': report_params
            }
        )
        
        # Generate report file
        file_content, filename = service.generate_report_file(
            report=report,
            data=report_data,
            format=report_params.get('format', 'pdf')
        )
        
        # Save file
        file_path = f"reports/{tenant.id}/{filename}"
        saved_path = default_storage.save(file_path, ContentFile(file_content))
        
        # Update export job
        export_job.status = 'completed'
        export_job.file_path = saved_path
        export_job.file_size = len(file_content)
        export_job.completed_at = timezone.now()
        export_job.expires_at = timezone.now() + timedelta(days=30)
        export_job.save()
        
        logger.info(f"Report generated: {report.name}")
        
        return {
            'status': 'completed',
            'export_job_id': export_job.id,
            'report_name': report.name,
            'file_size': export_job.file_size
        }
        
    except Exception as e:
        logger.error(f"Report generation failed: {e}")
        raise


@shared_task(base=TenantAwareTask, bind=True)
def export_campaign_data_task(self, tenant_id, campaign_id, export_format='excel'):
    """
    Export campaign performance data
    """
    try:
        tenant = get_tenant_by_id(tenant_id)
        campaign = Campaign.objects.get(id=campaign_id, tenant=tenant)
        service = ExportService(tenant=tenant)
        
        # Generate campaign export data
        export_data = service.export_campaign_data(
            campaign=campaign,
            include_members=True,
            include_analytics=True
        )
        
        # Create export job
        export_job = ExportJob.objects.create(
            tenant=tenant,
            export_type='campaign',
            created_by=campaign.created_by,
            config={
                'campaign_id': campaign.id,
                'format': export_format
            }
        )
        
        # Generate file
        if export_format == 'excel':
            file_content, filename = self._generate_campaign_excel(export_data, campaign)
        elif export_format == 'csv':
            file_content, filename = self._generate_campaign_csv(export_data, campaign)
        else:
            file_content, filename = self._generate_campaign_json(export_data, campaign)
        
        # Save file
        file_path = f"campaigns/{tenant.id}/{filename}"
        saved_path = default_storage.save(file_path, ContentFile(file_content))
        
        # Update export job
        export_job.status = 'completed'
        export_job.file_path = saved_path
        export_job.file_size = len(file_content)
        export_job.completed_at = timezone.now()
        export_job.expires_at = timezone.now() + timedelta(days=14)
        export_job.save()
        
        return {
            'status': 'completed',
            'export_job_id': export_job.id,
            'campaign_name': campaign.name
        }
        
    except Exception as e:
        logger.error(f"Campaign export failed: {e}")
        raise
    
    def _generate_campaign_excel(self, data, campaign):
        """Generate Excel file for campaign data"""
        buffer = io.BytesIO()
        
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            # Campaign overview
            overview_df = pd.DataFrame([{
                'Campaign Name': campaign.name,
                'Type': campaign.campaign_type,
                'Status': campaign.status,
                'Start Date': campaign.start_date,
                'End Date': campaign.end_date,
                'Budget': campaign.budget,
                'Actual Cost': campaign.actual_cost,
                'ROI': f"{campaign.roi_percentage or 0}%",
                'Members': data.get('member_count', 0),
                'Opens': data.get('email_opens', 0),
                'Clicks': data.get('email_clicks', 0),
                'Conversions': data.get('conversions', 0)
            }])
            overview_df.to_excel(writer, sheet_name='Campaign Overview', index=False)
            
            # Campaign members
            ifdf = pd.DataFrame(data['members'])
                members_df.to_excel(writer, sheet_name='Campaign Members', index=False)
            
            # Performance metrics
            if 'metrics''])
                metrics_df.to_excel(writer, sheet_name='Performance Metrics', index=False)
        
        filename = f"campaign_{campaign.name.replace(' ', '_')}_{timezone.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        return buffer.getvalue(), filename


@shared_task(base=CacheAwareTask, bind=True)
def export_analytics_dashboard_task(self, tenant_id, dashboard_config):
    """
    Export analytics dashboard data
    """
    try:
        tenant = get_tenant_by_id(tenant_id)
        service = ExportService(tenant=tenant)
        
        # Check cache first
        cache_key = f"dashboard_export_{tenant.id}_{hash(str(dashboard_config))}"
        cached_result = self.get_cached_result(cache_key)
        if cached_result:
            return cached_result
        
        # Generate dashboard data
        dashboard_data = service.export_analytics_dashboard(
            config=dashboard_config,
            tenant=tenant
        )
        
        # Create comprehensive export
        export_package = self._create_dashboard_export_package(dashboard_data, tenant)
        
        # Cache result for 1 hour
        result = {
            'status': 'completed',
            'export_package': export_package,
            'generated_at': timezone.now().isoformat()
        }
        
        self.set_cached_result(result, timeout=3600, cache_key=cache_key)
        
        return result
        
    except Exception as e:
        logger.error(f"Dashboard export failed: {e}")
        raise
    
    def _create_dashboard_export_package(self, data, tenant):
        """Create a comprehensive dashboard export package"""
        # Create temporary directory for files
        temp_dir = f"/tmp/dashboard_export_{tenant.id}_{timezone.now().strftime('%Y%m%d_%H%M%S')}"
        os.makedirs(temp_dir, exist_ok=True)
        
        try:
            # Generate individual files
            files_created = []
            
            # Executive summary
            if
                summary_file = os.path.join(temp_dir, 'executive_summary.json')
                with open(summary_file, 'w') as f:
                    json.dump(data['executive_summary'], f, indent=2, default=str)
                files_created.append(summary_file)
            
            # Sales data
            if 'sales_datadf = pd.DataFrame(data['sales_data'])
                sales_file = os.path.join(temp_dir, 'sales_data.xlsx')
                sales_df.to_excel(sales_file, index=False)
                files_created.append(sales_file)
            
            # Marketing data
            if 'marketing_data' in pd.DataFrame(data['marketing_data'])
                marketing_file = os.path.join(temp_dir, 'marketing_data.xlsx')
                marketing_df.to_excel(marketing_file, index=False)
                files_created.append(marketing_file)
            
            # Create ZIP package
            zip_filename = f"dashboard_export_{tenant.name.replace(' ', '_')}_{timezone.now().strftime('%Y%m%d_%H%M%S')}.zip"
            zip_path = os.path.join(temp_dir, zip_filename)
            
            with zipfile.ZipFile(zip_path, 'w') as zipf:
                for file_path in files_created:
                    zipf.write(file_path, os.path.basename(file_path))
            
            # Upload to storage
            with open(zip_path, 'rb') as zip_file:
                storage_path = f"dashboard_exports/{tenant.id}/{zip_filename}"
                saved_path = default_storage.save(storage_path, zip_file)
            
            # Clean up temp files
            import shutil
            shutil.rmtree(temp_dir)
            
            return {
                'file_path': saved_path,
                'filename': zip_filename,
                'files_included': [os.path.basename(f) for f in files_created]
            }
            
        except Exception as e:
            # Clean up on error
            import shutil
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
            raise


@shared_task(base=TenantAwareTask, bind=True)
def cleanup_expired_exports_task(self, tenant_id=None):
    """
    Clean up expired export files
    """
    try:
        # Find expired export jobs
        expired_jobs = ExportJob.objects.filter(
            expires_at__lt=timezone.now(),
            file_path__isnull=False
        )
        
        if tenant_id:
            tenant = get_tenant_by_id(tenant_id)
            expired_jobs = expired_jobs.filter(tenant=tenant)
        
        cleaned_count = 0
        space_freed = 0
        
        for job in expired_jobs:
            try:
                # Delete file from storage
                if job.file_path:
                    try:
                        file_size = default_storage.size(job.file_path)
                        default_storage.delete(job.file_path)
                        space_freed += file_size
                    except:
                        pass
                
                # Clear file path from job
                job.file_path = None
                job.save(update_fields=['file_path'])
                cleaned_count += 1
                
            except Exception as e:
                logger.error(f"Failed to cleanup export job {job.id}: {e}")
        
        logger.info(f"Cleaned up {cleaned_count} expired exports, freed {space_freed} bytes")
        
        return {
            'status': 'completed',
            'cleaned_count': cleaned_count,
            'space_freed': space_freed
        }
        
    except Exception as e:
        logger.error(f"Export cleanup task failed: {e}")
        raise