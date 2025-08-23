"""
Import Tasks
Handle data import, processing, and validation from various sources
"""

from celery import shared_task
from django.db import transaction, IntegrityError
from django.utils import timezone
from django.core.files.storage import default_storage
from django.conf import settings
import logging
import pandas as pd
import csv
import json
from datetime import datetime
from typing import List, Dict, Any

from .base import TenantAwareTask, BatchProcessingTask, MonitoredTask
from ..models import (
    Lead, Contact, Account, Product, Activity, 
    ImportJob, ImportError, DataTemplate
)
from ..services.import_service import ImportService
from ..utils.tenant_utils import get_tenant_by_id
from ..utils.validators import validate_email, validate_phone

logger = logging.getLogger(__name__)


@shared_task(base=BatchProcessingTask, bind=True)
def import_leads_task(self, tenant_id, file_path, import_job_id, mapping_config=None, batch_size=100):
    """
    Import leads from CSV/Excel file
    """
    try:
        tenant = get_tenant_by_id(tenant_id)
        service = ImportService(tenant=tenant)
        
        # Get import job
        import_job = ImportJob.objects.get(id=import_job_id, tenant=tenant)
        import_job.status = 'processing'
        import_job.started_at = timezone.now()
        import_job.save(update_fields=['status', 'started_at'])
        
        # Read file
        file_extension = file_path.split('.')[-1].lower()
        
        if file_extension == 'csv':
            data = pd.read_csv(file_path)
        elif file_extension in ['xlsx', 'xls']:
            data = pd.read_excel(file_path)
        else:
            raise ValueError(f"Unsupported file format: {file_extension}")
        
        # Apply column mapping
        if mapping_config:
            data = data.rename(columns=mapping_config)
        
        # Convert to list of dictionaries
        records = data.to_dict('records')
        
        def process_lead_batch(batch):
            """Process a batch of lead records"""
            created_leads = []
            errors = []
            
            for i, record in enumerate(batch):
                try:
                    # Validate and clean data
                    lead_data = self._prepare_lead_data(record, tenant)
                    
                    # Check for duplicates
                    if self._is_duplicate_lead(lead_data, tenant):
                        errors.append({
                            'row': i + 1,
                            'error': 'Duplicate lead found',
                            'data': record
                        })
                        continue
                    
                    # Create lead
                    lead = Lead.objects.create(**lead_data)
                    created_leads.append(lead)
                    
                    # Update import job progress
                    import_job.processed_count = (import_job.processed_count or 0) + 1
                    
                except Exception as e:
                    errors.append({
                        'row': i + 1,
                        'error': str(e),
                        'data': record
                    })
                    import_job.error_count = (import_job.error_count or 0) + 1
            
            # Bulk save import job progress
            import_job.success_count = (import_job.success_count or 0) + len(created_leads)
            import_job.save(update_fields=['processed_count', 'success_count', 'error_count'])
            
            # Save errors
            for error in errors:
                ImportError.objects.create(
                    import_job=import_job,
                    row_number=error['row'],
                    error_message=error['error'],
                    raw_data=error['data']
                )
            
            return len(created_leads)
        
        # Process in batches
        result = self.process_in_batches(
            records,
            batch_size=batch_size,
            process_func=process_lead_batch
        )
        
        # Update import job status
        import_job.status = 'completed' if result['error_count'] == 0 else 'completed_with_errors'
        import_job.completed_at = timezone.now()
        import_job.total_records = len(records)
        import_job.result_summary = result
        import_job.save()
        
        # Clean up file
        try:
            default_storage.delete(file_path)
        except:
            pass
        
        logger.info(f"Lead import completed: {result['processed_items']} processed, {result['error_count']} errors")
        
        return result
        
    except Exception as e:
        # Update import job with error
        try:
            import_job = ImportJob.objects.get(id=import_job_id)
            import_job.status = 'failed'
            import_job.error_message = str(e)
            import_job.completed_at = timezone.now()
            import_job.save()
        except:
            pass
        
        logger.error(f"Lead import task failed: {e}")
        raise
    
    def _prepare_lead_data(self, record, tenant):
        """Prepare and validate lead data"""
        # Map common field variations
        field_mapping = {
            'first_name': ['first_name', 'firstname', 'First Name', 'fname'],
            'last_name': ['last_name', 'lastname', 'Last Name', 'lname'],
            'email': ['email', 'Email', 'email_address', 'Email Address'],
            'phone': ['phone', 'Phone', 'phone_number', 'Phone Number'],
            'company': ['company', 'Company', 'company_name', 'Company Name'],
            'title': ['title', 'Title', 'job_title', 'Job Title'],
            'website': ['website', 'Website', 'company_website'],
            'industry': ['industry', 'Industry'],
            'country': ['country', 'Country'],
            'state': ['state', 'State', 'province', 'Province'],
            'city': ['city', 'City']
        }
        
        lead_data = {'tenant': tenant}
        
        for field, variations in field_mapping.items():
            for variation in variations:
                if variation in record and pd.notna(record[variation]):
                    value = str(record[variation]).strip()
                    if value:
                        lead_data[field] = value
                        break
        
        # Validate required fields
        if not lead_data.get('email') and not lead_data.get('phone'):
            raise ValueError("Either email or phone is required")
        
        # Validate email format
        if 
            if not validate_email(lead_data['email']):
                raise ValueError(f"Invalid email format: {lead_data['email']}")
        
        # Validate phone format
        if 'phone' in lea']):
                raise ValueError(f"Invalid phone format: {lead_data['phone']}")
        
        # Set defaults
        lead_data.setdefault('status', 'new')
        lead_data.setdefault('source', self._get_or_create_import_source())
        
        return lead_data
    
    def _is_duplicate_lead(self, lead_data, tenant):
        """Check for duplicate leads"""
        if
            if Lead.objects.filter(tenant=tenant, email=lead_data['email']).exists():
                
            if Lead.objects.filter(tenant=tenant, phone=lead_data['phone']).exists():
                return True
        
        return False
    
    def _get_or_create_import_source(self):
        """Get or create import source"""
        from ..models import LeadSource
        source, created = LeadSource.objects.get_or_create(
            name='Data Import',
            defaults={'description': 'Imported from file'}
        )
        return source


@shared_task(base=BatchProcessingTask, bind=True)
def import_contacts_task(self, tenant_id, file_path, import_job_id, mapping_config=None, batch_size=100):
    """
    Import contacts from CSV/Excel file
    """
    try:
        tenant = get_tenant_by_id(tenant_id)
        service = ImportService(tenant=tenant)
        
        # Get import job
        import_job = ImportJob.objects.get(id=import_job_id, tenant=tenant)
        import_job.status = 'processing'
        import_job.started_at = timezone.now()
        import_job.save(update_fields=['status', 'started_at'])
        
        # Read file
        file_extension = file_path.split('.')[-1].lower()
        
        if file_extension == 'csv':
            data = pd.read_csv(file_path)
        elif file_extension in ['xlsx', 'xls']:
            data = pd.read_excel(file_path)
        else:
            raise ValueError(f"Unsupported file format: {file_extension}")
        
        # Apply column mapping
        if mapping_config:
            data = data.rename(columns=mapping_config)
        
        records = data.to_dict('records')
        
        def process_contact_batch(batch):
            """Process a batch of contact records"""
            created_contacts = []
            errors = []
            
            for i, record in enumerate(batch):
                try:
                    # Prepare contact data
                    contact_data = self._prepare_contact_data(record, tenant)
                    
                    # Check for duplicates
                    if self._is_duplicate_contact(contact_data, tenant):
                        errors.append({
                            'row': i + 1,
                            'error': 'Duplicate contact found',
                            'data': record
                        })
                        continue
                    
                    # Create contact
                    contact = Contact.objects.create(**contact_data)
                    created_contacts.append(contact)
                    
                    import_job.processed_count = (import_job.processed_count or 0) + 1
                    
                except Exception as e:
                    errors.append({
                        'row': i + 1,
                        'error': str(e),
                        'data': record
                    })
                    import_job.error_count = (import_job.error_count or 0) + 1
            
            # Update progress
            import_job.success_count = (import_job.success_count or 0) + len(created_contacts)
            import_job.save(update_fields=['processed_count', 'success_count', 'error_count'])
            
            # Save errors
            for error in errors:
                ImportError.objects.create(
                    import_job=import_job,
                    row_number=error['row'],
                    error_message=error['error'],
                    raw_data=error['data']
                )
            
            return len(created_contacts)
        
        # Process in batches
        result = self.process_in_batches(
            records,
            batch_size=batch_size,
            process_func=process_contact_batch
        )
        
        # Update import job
        import_job.status = 'completed' if result['error_count'] == 0 else 'completed_with_errors'
        import_job.completed_at = timezone.now()
        import_job.total_records = len(records)
        import_job.result_summary = result
        import_job.save()
        
        # Clean up file
        try:
            default_storage.delete(file_path)
        except:
            pass
        
        logger.info(f"Contact import completed: {result['processed_items']} processed")
        
        return result
        
    except Exception as e:
        # Update import job with error
        try:
            import_job = ImportJob.objects.get(id=import_job_id)
            import_job.status = 'failed'
            import_job.error_message = str(e)
            import_job.save()
        except:
            pass
        
        logger.error(f"Contact import task failed: {e}")
        raise
    
    def _prepare_contact_data(self, record, tenant):
        """Prepare contact data from record"""
        contact_data = {'tenant': tenant}
        
        # Similar field mapping as leads
        field_mapping = {
            'first_name': ['first_name', 'firstname', 'First Name'],
            'last_name': ['last_name', 'lastname', 'Last Name'],
            'email': ['email', 'Email', 'email_address'],
            'phone': ['phone', 'Phone', 'phone_number'],
            'title': ['title', 'Title', 'job_title'],
            'company': ['company', 'Company', 'company_name'],
            'department': ['department', 'Department'],
            'address': ['address', 'Address', 'street_address'],
            'city': ['city', 'City'],
            'state': ['state', 'State'],
            'country': ['country', 'Country'],
            'postal_code': ['postal_code', 'zip', 'zipcode', 'Postal Code']
        }
        
        for field, variations in field_mapping.items():
            for variation in variations:
                if variation in record and pd.notna(record[variation]):
                    value = str(record[variation]).strip()
                    if value:
                        contact_data[field] = value
                        break
        
        # Try to find or create associated account
        ifaccount = self._find_or_create_account(contact_data['company'], tenant)
            contact_data['account'] = account
        
        # Validate email
        if 'email' in contact_data and not validate_email(contact_data['email']):
            raise ValueError(f"Invalid email: {contact_data['email']}")
        
        return contact_data
    
    def _is_duplicate_contact(self, contact_data, tenant):
        """Check for duplicate contacts"""
        if 'email' in contacttenant, email=contact_data['email']).exists()
        return False
    
    def _find_or_create_account(self, company_name, tenant):
        """Find existing account or create new one"""
        try:
            return Account.objects.get(tenant=tenant, name__iexact=company_name)
        except Account.DoesNotExist:
            return Account.objects.create(
                tenant=tenant,
                name=company_name,
                account_type='prospect'
            )


@shared_task(base=MonitoredTask, bind=True)
def process_bulk_upload_task(self, tenant_id, upload_id, file_type='leads'):
    """
    Process bulk file upload with intelligent data detection
    """
    try:
        tenant = get_tenant_by_id(tenant_id)
        service = ImportService(tenant=tenant)
        
        # Get upload record
        from ..models import BulkUpload
        upload = BulkUpload.objects.get(id=upload_id, tenant=tenant)
        
        upload.status = 'processing'
        upload.started_at = timezone.now()
        upload.save(update_fields=['status', 'started_at'])
        
        # Analyze file structure
        analysis = service.analyze_file_structure(upload.file.path)
        
        # Auto-detect field mappings
        field_mappings = service.detect_field_mappings(
            analysis['columns'],
            target_type=file_type
        )
        
        # Validate data quality
        quality_report = service.analyze_data_quality(
            upload.file.path,
            field_mappings
        )
        
        # Create import job
        import_job = ImportJob.objects.create(
            tenant=tenant,
            import_type=file_type,
            file_name=upload.original_filename,
            mapping_config=field_mappings,
            quality_report=quality_report,
            created_by=upload.created_by
        )
        
        # Start appropriate import task
        if file_type == 'leads':
            import_leads_task.delay(
                tenant_id=tenant.id,
                file_path=upload.file.path,
                import_job_id=import_job.id,
                mapping_config=field_mappings
            )
        elif file_type == 'contacts':
            import_contacts_task.delay(
                tenant_id=tenant.id,
                file_path=upload.file.path,
                import_job_id=import_job.id,
                mapping_config=field_mappings
            )
        elif file_type == 'products':
            import_products_task.delay(
                tenant_id=tenant.id,
                file_path=upload.file.path,
                import_job_id=import_job.id,
                mapping_config=field_mappings
            )
        
        # Update upload record
        upload.status = 'processing'
        upload.import_job = import_job
        upload.analysis_result = {
            'structure': analysis,
            'mappings': field_mappings,
            'quality': quality_report
        }
        upload.save()
        
        return {
            'status': 'started',
            'import_job_id': import_job.id,
            'analysis': analysis,
            'mappings': field_mappings,
            'quality_report': quality_report
        }
        
    except Exception as e:
        # Update upload with error
        try:
            upload = BulkUpload.objects.get(id=upload_id)
            upload.status = 'failed'
            upload.error_message = str(e)
            upload.save()
        except:
            pass
        
        logger.error(f"Bulk upload processing failed: {e}")
        raise


@shared_task(base=BatchProcessingTask, bind=True)
def import_products_task(self, tenant_id, file_path, import_job_id, mapping_config=None, batch_size=50):
    """
    Import products from CSV/Excel file
    """
    try:
        tenant = get_tenant_by_id(tenant_id)
        
        # Get import job
        import_job = ImportJob.objects.get(id=import_job_id, tenant=tenant)
        import_job.status = 'processing'
        import_job.started_at = timezone.now()
        import_job.save(update_fields=['status', 'started_at'])
        
        # Read file
        file_extension = file_path.split('.')[-1].lower()
        
        if file_extension == 'csv':
            data = pd.read_csv(file_path)
        elif file_extension in ['xlsx', 'xls']:
            data = pd.read_excel(file_path)
        
        # Apply mapping
        if mapping_config:
            data = data.rename(columns=mapping_config)
        
        records = data.to_dict('records')
        
        def process_product_batch(batch):
            """Process a batch of product records"""
            created_products = []
            errors = []
            
            for i, record in enumerate(batch):
                try:
                    product_data = self._prepare_product_data(record, tenant)
                    
                    # Check for duplicate SKU
                    if Product.objects.filter(
                        tenant=tenant, 
                        sku=product_data.get('sku')
                    ).exists():
                        errors.append({
                            'row': i + 1,
                            'error': f"Duplicate SKU: {product_data.get('sku')}",
                            'data': record
                        })
                        continue
                    
                    product = Product.objects.create(**product_data)
                    created_products.append(product)
                    
                    import_job.processed_count = (import_job.processed_count or 0) + 1
                    
                except Exception as e:
                    errors.append({
                        'row': i + 1,
                        'error': str(e),
                        'data': record
                    })
                    import_job.error_count = (import_job.error_count or 0) + 1
            
            # Update progress
            import_job.success_count = (import_job.success_count or 0) + len(created_products)
            import_job.save(update_fields=['processed_count', 'success_count', 'error_count'])
            
            # Save errors
            for error in errors:
                ImportError.objects.create(
                    import_job=import_job,
                    row_number=error['row'],
                    error_message=error['error'],
                    raw_data=error['data']
                )
            
            return len(created_products)
        
        # Process in batches
        result = self.process_in_batches(
            records,
            batch_size=batch_size,
            process_func=process_product_batch
        )
        
        # Update import job
        import_job.status = 'completed' if result['error_count'] == 0 else 'completed_with_errors'
        import_job.completed_at = timezone.now()
        import_job.total_records = len(records)
        import_job.save()
        
        logger.info(f"Product import completed: {result['processed_items']} processed")
        
        return result
        
    except Exception as e:
        logger.error(f"Product import task failed: {e}")
        raise
    
    def _prepare_product_data(self, record, tenant):
        """Prepare product data from record"""
        product_data = {'tenant': tenant}
        
        # Product field mapping
        field_mapping = {
            'name': ['name', 'product_name', 'Product Name'],
            'sku': ['sku', 'SKU', 'product_code', 'Product Code'],
            'description': ['description', 'Description'],
            'base_price': ['price', 'base_price', 'Price', 'Base Price'],
            'cost': ['cost', 'Cost'],
            'category': ['category', 'Category', 'product_category'],
            'brand': ['brand', 'Brand'],
            'weight': ['weight', 'Weight'],
            'dimensions': ['dimensions', 'Dimensions']
        }
        
        for field, variations in field_mapping.items():
            for variation in variations:
                if variation in record and pd.notna(record[variation]):
                    value = record[variation]
                    
                    # Convert price fields to decimal
                    if field in ['base_price', 'cost'] and value:
                        try:
                            value = float(str(value).replace('$', '').replace(',', ''))
                        except (ValueError, TypeError):
                            continue
                    
                    if value:
                        product_data[field] = value
                        break
        
        # Find or create category
        if 'category' in product_data:
            category_name = product_data.pop('category')
            category = self._find_or_create_category(category_name, tenant)
            product_data['category'] = category
        
        # Validate required fields
        if not product_data.get('name'):
            raise ValueError("Product name is required")
        
        if not product_data.get('sku'):
            raise ValueError("Product SKU is required")
        
        return product_data
    
    def _find_or_create_category(self, category_name, tenant):
        """Find or create product category"""
        from ..models import ProductCategory
        
        try:
            return ProductCategory.objects.get(tenant=tenant, name__iexact=category_name)
        except ProductCategory.DoesNotExist:
            return ProductCategory.objects.create(
                tenant=tenant,
                name=category_name
            )


@shared_task(base=TenantAwareTask, bind=True)
def import_from_api_task(self, tenant_id, api_config, import_type='leads'):
    """
    Import data from external API
    """
    try:
        tenant = get_tenant_by_id(tenant_id)
        service = ImportService(tenant=tenant)
        
        # Fetch data from API
        api_data = service.fetch_from_api(api_config)
        
        # Create import job
        import_job = ImportJob.objects.create(
            tenant=tenant,
            import_type=f"{import_type}_api",
            source=api_config.get('source', 'External API'),
            total_records=len(api_data)
        )
        
        # Process data based on type
        if import_type == 'leads':
            result = service.process_api_leads(api_data, import_job)
        elif import_type == 'contacts':
            result = service.process_api_contacts(api_data, import_job)
        
        # Update import job
        import_job.status = 'completed'
        import_job.completed_at = timezone.now()
        import_job.result_summary = result
        import_job.save()
        
        return result
        
    except Exception as e:
        logger.error(f"API import task failed: {e}")
        raise


@shared_task(base=TenantAwareTask, bind=True)
def validate_import_data_task(self, tenant_id, import_job_id):
    """
    Validate imported data and generate quality report
    """
    try:
        tenant = get_tenant_by_id(tenant_id)
        import_job = ImportJob.objects.get(id=import_job_id, tenant=tenant)
        service = ImportService(tenant=tenant)
        
        # Run validation based on import type
        if import_job.import_type == 'leads':
            validation_result = service.validate_imported_leads(import_job)
        elif import_job.import_type == 'contacts':
            validation_result = service.validate_imported_contacts(import_job)
        elif import_job.import_type == 'products':
            validation_result = service.validate_imported_products(import_job)
        
        # Update import job with validation results
        import_job.validation_result = validation_result
        import_job.save(update_fields=['validation_result'])
        
        return validation_result
        
    except Exception as e:
        logger.error(f"Import validation task failed: {e}")
        raise