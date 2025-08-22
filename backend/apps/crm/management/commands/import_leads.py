"""
Bulk Lead Import Management Command
Handles CSV/Excel import with validation, deduplication, and error reporting.
"""

import csv
import json
import logging
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Dict, List, Tuple, Any

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from django.core.validators import validate_email
from django.core.exceptions import ValidationError

from crm.models.lead_model import Lead, LeadSource
from crm.models.user_model import CRMUserProfile
from crm.services.lead_service import LeadService

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Import leads from CSV file with validation and deduplication'

    def add_arguments(self, parser):
        parser.add_argument(
            '--file',
            type=str,
            help='Path to CSV file containing leads',
            required=True
        )
        
        parser.add_argument(
            '--mapping',
            type=str,
            help='JSON file containing field mapping configuration',
            default=None
        )
        
        parser.add_argument(
            '--batch-size',
            type=int,
            help='Number of leads to process in each batch',
            default=100
        )
        
        parser.add_argument(
            '--skip-duplicates',
            action='store_true',
            help='Skip duplicate leads instead of updating them',
        )
        
        parser.add_argument(
            '--update-existing',
            action='store_true',
            help='Update existing leads with new data',
        )
        
        parser.add_argument(
            '--default-source',
            type=str,
            help='Default lead source for imported leads',
            default='Import'
        )
        
        parser.add_argument(
            '--default-owner',
            type=str,
            help='Default owner email for imported leads',
            default=None
        )
        
        parser.add_argument(
            '--validate-only',
            action='store_true',
            help='Only validate data without importing',
        )
        
        parser.add_argument(
            '--error-file',
            type=str,
            help='Path to save error report',
            default='lead_import_errors.csv'
        )

    def handle(self, *args, **options):
        try:
            self.lead_service = LeadService()
            self.import_leads(**options)
            
        except Exception as e:
            logger.error(f"Lead import failed: {str(e)}")
            raise CommandError(f'Lead import failed: {str(e)}')

    def import_leads(self, **options):
        """Main import orchestrator"""
        file_path = options['file']
        
        self.stdout.write(f'📂 Starting lead import from: {file_path}')
        
        # Load field mapping
        field_mapping = self._load_field_mapping(options.get('mapping'))
        
        # Read and validate CSV data
        leads_data, errors = self._read_csv_file(file_path, field_mapping)
        
        if errors:
            self._save_error_report(errors, options['error_file'])
            if options['validate_only']:
                self.stdout.write(
                    self.style.ERROR(
                        f'❌ Validation failed with {len(errors)} errors. '
                        f'Check {options["error_file"]} for details.'
                    )
                )
                return
        
        if options['validate_only']:
            self.stdout.write(
                self.style.SUCCESS(
                    f'✅ Validation successful! {len(leads_data)} leads ready to import.'
                )
            )
            return
        
        # Process leads in batches
        results = self._process_leads_in_batches(
            leads_data,
            options['batch_size'],
            options
        )
        
        # Print summary
        self._print_import_summary(results)

    def _load_field_mapping(self, mapping_file: str) -> Dict[str, str]:
        """Load field mapping configuration"""
        if not mapping_file:
            return self._get_default_field_mapping()
        
        try:
            with open(mapping_file, 'r') as f:
                mapping = json.load(f)
                self.stdout.write(f'✅ Loaded field mapping from: {mapping_file}')
                return mapping
        except FileNotFoundError:
            self.stdout.write(
                self.style.WARNING(f'⚠️ Mapping file not found: {mapping_file}')
            )
            return self._get_default_field_mapping()
        except json.JSONDecodeError as e:
            raise CommandError(f'Invalid JSON in mapping file: {str(e)}')

    def _get_default_field_mapping(self) -> Dict[str, str]:
        """Default field mapping for CSV columns to Lead model fields"""
        return {
            'first_name': 'first_name',
            'last_name': 'last_name',
            'email': 'email',
            'phone': 'phone',
            'company': 'company',
            'job_title': 'job_title',
            'industry': 'industry',
            'source': 'source',
            'status': 'status',
            'budget': 'budget',
            'notes': 'notes',
            'website': 'website',
            'address': 'address',
            'city': 'city',
            'state': 'state',
            'country': 'country',
            'postal_code': 'postal_code',
        }

    def _read_csv_file(self, file_path: str, field_mapping: Dict[str, str]) -> Tuple[List[Dict], List[Dict]]:
        """Read and validate CSV file"""
        leads_data = []
        errors = []
        
        try:
            with open(file_path, 'r', encoding='utf-8-sig') as csvfile:
                # Detect delimiter
                sample = csvfile.read(1024)
                csvfile.seek(0)
                sniffer = csv.Sniffer()
                delimiter = sniffer.sniff(sample).delimiter
                
                reader = csv.DictReader(csvfile, delimiter=delimiter)
                
                for row_num, row in enumerate(reader, start=2):  # Start at 2 (header is row 1)
                    try:
                        # Map CSV columns to model fields
                        lead_data = self._map_row_data(row, field_mapping)
                        
                        # Validate the mapped data
                        validation_errors = self._validate_lead_data(lead_data)
                        
                        if validation_errors:
                            errors.append({
                                'row': row_num,
                                'data': row,
                                'errors': validation_errors
                            })
                        else:
                            lead_data['_row_number'] = row_num
                            leads_data.append(lead_data)
                            
                    except Exception as e:
                        errors.append({
                            'row': row_num,
                            'data': row,
                            'errors': [f'Processing error: {str(e)}']
                        })
                
                self.stdout.write(f'📊 Read {len(leads_data)} valid leads, {len(errors)} errors')
                
        except FileNotFoundError:
            raise CommandError(f'CSV file not found: {file_path}')
        except Exception as e:
            raise CommandError(f'Error reading CSV file: {str(e)}')
        
        return leads_data, errors

    def _map_row_data(self, row: Dict[str, str], field_mapping: Dict[str, str]) -> Dict[str, Any]:
        """Map CSV row to Lead model fields"""
        lead_data = {}
        
        for csv_column, model_field in field_mapping.items():
            if csv_column in row and row[csv_column]:
                value = row[csv_column].strip()
                
                # Type conversion based on field
                if model_field == 'budget':
                    try:
                        # Remove currency symbols and convert to decimal
                        cleaned_value = value.replace('$', '').replace(',', '').strip()
                        lead_data[model_field] = Decimal(cleaned_value)
                    except (InvalidOperation, ValueError):
                        # Will be caught in validation
                        lead_data[model_field] = value
                
                elif model_field in ['phone']:
                    # Clean phone numbers
                    lead_data[model_field] = self._clean_phone_number(value)
                
                elif model_field == 'email':
                    lead_data[model_field] = value.lower()
                
                else:
                    lead_data[model_field] = value
        
        return lead_data

    def _clean_phone_number(self, phone: str) -> str:
        """Clean and format phone number"""
        # Remove common formatting characters
        cleaned = ''.join(char for char in phone if char.isdigit() or char in ['+', '-', '(', ')', ' '])
        return cleaned.strip()

    def _validate_lead_data(self, lead_data: Dict[str, Any]) -> List[str]:
        """Validate lead data and return list of errors"""
        errors = []
        
        # Required fields validation
        required_fields = ['first_name', 'last_name', 'email']
        for field in required_fields:
            if not lead_data.get(field):
                errors.append(f'Missing required field: {field}')
        
        # Email validation
        if lead_data.get('email'):
            try:
                validate_email(lead_data['email'])
            except ValidationError:
                errors.append(f'Invalid email format: {lead_data["email"]}')
        
        # Budget validation
        if lead_data.get('budget'):
            if not isinstance(lead_data['budget'], Decimal):
                try:
                    Decimal(str(lead_data['budget']))
                except (InvalidOperation, ValueError):
                    errors.append(f'Invalid budget format: {lead_data["budget"]}')
        
        # Status validation
        valid_statuses = ['NEW', 'CONTACTED', 'QUALIFIED', 'UNQUALIFIED', 'CONVERTED']
        if lead_data.get('status') and lead_data['status'].upper() not in valid_statuses:
            errors.append(f'Invalid status: {lead_data["status"]}. Must be one of: {", ".join(valid_statuses)}')
        
        return errors

    def _process_leads_in_batches(self, batch_size: int, options: Dict) -> Dict[str, int]:
        """Process leads in batches"""
        total_leads = len(leads_data)
        processed = 0
        created = 0
        updated = 0
        skipped = 0
        errors = 0
        
        # Get default source and owner
        default_source = self._get_or_create_lead_source(options['default_source'])
        default_owner = self._get_default_owner(options.get('default_owner'))
        
        for i in range(0, total_leads, batch_size):
            batch = leads_data[i:i + batch_size]
            batch_results = self._process_batch(batch, default_source, default_owner, options)
            
            created += batch_results['created']
            updated += batch_results['updated']
            skipped += batch_results['skipped']
            errors += batch_results['errors']
            processed += len(batch)
            
            # Progress update
            progress = (processed / total_leads) * 100
            self.stdout.write(f'📈 Progress: {progress:.1f}% ({processed}/{total_leads})')
        
        return {
            'total': total_leads,
            'created': created,
            'updated': updated,
            'skipped': skipped,
            'errors': errors
        }

    def _process_batch(self, batch: List[Dict], default_source, default_owner, options: Dict) -> Dict[str, int]:
        """Process a single batch of leads"""
        results = {'created': 0, 'updated': 0, 'skipped': 0, 'errors': 0}
        
        with transaction.atomic():
            for lead_data in batch:
                try:
                    # Check for existing lead
                    existing_lead = self._find_existing_lead(lead_data)
                    
                    if existing_lead:
                        if options['skip_duplicates']:
                            results['skipped'] += 1
                            continue
                        elif options['update_existing']:
                            self._update_existing_lead(existing_lead, lead_data, default_source, default_owner)
                            results['updated'] += 1
                        else:
                            results['skipped'] += 1
                    else:
                        # Create new lead
                        self._create_new_lead(lead_data, default_source, default_owner)
                        results['created'] += 1
                        
                except Exception as e:
                    logger.error(f"Error processing lead {lead_data.get('email', 'unknown')}: {str(e)}")
                    results['errors'] += 1
        
        return results

    def _find_existing_lead(self,d:
        """Find existing lead by email"""
        email = lead_data.get('email')
        if email:
            return Lead.objects.filter(email__iexact=email).first()
        return None

    def _create_new_lead(self, lea, default_owner):
        """Create a new lead"""
        # Prepare lead data
        lead_kwargs = {
            'first_name': lead_data.get('first_name', ''),
            'last_name': lead_data.get('last_name', ''),
            'email': lead_data.get('email', ''),
            'phone': lead_data.get('phone', ''),
            'company': lead_data.get('company', ''),
            'job_title': lead_data.get('job_title', ''),
            'industry': lead_data.get('industry', ''),
            'status': lead_data.get('status', 'NEW').upper(),
            'source': default_source,
            'notes': lead_data.get('notes', ''),
            'website': lead_data.get('website', ''),
            'address': lead_data.get('address', ''),
            'city': lead_data.get('city', ''),
            'state': lead_data.get('state', ''),
            'country': lead_data.get('country', ''),
            'postal_code': lead_data.get('postal_code', ''),
        }
        
        # Add budget if provided
        if lead_data.get('budget'):
            lead_kwargs['budget'] = lead_data['budget']
        
        # Add owner if provided
        if default_owner:
            lead_kwargs['assigned_to'] = default_owner
        
        # Create lead using service (includes scoring and workflow triggers)
        lead = self.lead_service.create_lead(lead_kwargs)
        
        return lead

    def _update_existing_lead(self, existing_lea, default_source, default_owner):
        """Update existing lead with new data"""
        update_fields = []
        
        # Update non-empty fields
        field_mapping = {
            'first_name': 'first_name',
            'last_name': 'last_name',
            'phone': 'phone',
            'company': 'company',
            'job_title': 'job_title',
            'industry': 'industry',
            'website': 'website',
            'address': 'address',
            'city': 'city',
            'state': 'state',
            'country': 'country',
            'postal_code': 'postal_code',
        }
        
        for data_field, model_field in field_mapping.items():
            if lead_data.get(data_field):
                setattr(existing_lead, model_field, lead_data[data_field])
                update_fields.append(model_field)
        
        # Update budget if provided
        if lead_data.get('budget'):
            existing_lead.budget = lead_data['budget']
            update_fields.append('budget')
        
        # Append to notes if provided
        if lead_data.get('notes'):
            current_notes = existing_lead.notes or ''
            import_note = f"\n\n[Import {timezone.now().strftime('%Y-%m-%d %H:%M')}]: {lead_data['notes']}"
            existing_lead.notes = current_notes + import_note
            update_fields.append('notes')
        
        if update_fields:
            update_fields.append('updated_at')
            existing_lead.save(update_fields=update_fields)
        
        return existing_lead

    def _get_or_create_lead_source(self, source_name: str):
        """Get or create lead source"""
        source, created = LeadSource.objects.get_or_create(
            name=source_name,
            defaults={
                'cost_per_lead': Decimal('0.00'),
                'is_active': True
            }
        )
        
        if created:
            self.stdout.write(f'✅ Created new lead source: {source_name}')
        
        return source

    def _get_default_owner(self, owner_email: str):
        """Get default owner for imported leads"""
        if not owner_email:
            return None
        
        try:
            user_profile = CRMUserProfile.objects.get(user__email=owner_email)
            return user_profile
        except CRMUserProfile.DoesNotExist:
            self.stdout.write(
                self.style.WARNING(f'⚠️ Default owner not found: {owner_email}')
            )
            return None

    def _save_error_report(self, errors: List[Dict], error_file: str):
        """Save error report to CSV file"""
        if not errors:
            return
        
        with open(error_file, 'w', newline='', encoding='utf-8') as csvfile:
            fieldnames = ['row', 'error', 'data']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            
            writer.writeheader()
            for error in errors:
                for err_msg in error['errors']:
                    writer.writerow({
                        'row': error['row'],
                        'error': err_msg,
                        'data': json.dumps(error['data'])
                    })
        
        self.stdout.write(f'💾 Error report saved to: {error_file}')

    def _print_import_summary(self, results: Dict[str, int]):
        """Print import summary"""
        self.stdout.write('\n' + '='*60)
        self.stdout.write('📊 IMPORT SUMMARY')
        self.stdout.write('='*60)
        self.stdout.write(f'Total Processed: {results["total"]}')
        self.stdout.write(self.style.SUCCESS(f'✅ Created: {results["created"]}'))
        self.stdout.write(self.style.WARNING(f'🔄 Updated: {results["updated"]}'))
        self.stdout.write(self.style.WARNING(f'⏭️ Skipped: {results["skipped"]}'))
        self.stdout.write(self.style.ERROR(f'❌ Errors: {results["errors"]}'))
        self.stdout.write('='*60)
        
        success_rate = ((results['created'] + results['updated']) / results['total']) * 100
        self.stdout.write(f'Success Rate: {success_rate:.1f}%')