"""
Comprehensive Data Export Management Command
Exports CRM data with advanced filtering, multiple formats, and scheduling support.
"""

import csv
import json
import logging
import os
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Any, Optional
import zipfile
from io import StringIO, BytesIO

from django.core.management.base import BaseCommand, CommandError
from django.db import models
from django.utils import timezone
from django.core.serializers import serialize
from django.apps import apps
from django.db.models import Q, Count, Sum, Avg
from django.template.loader import render_to_string

try:
    import xlsxwriter
    EXCEL_AVAILABLE = True
except ImportError:
    EXCEL_AVAILABLE = False

from crm.models.lead_model import Lead, LeadSource
from crm.models.account_model import Account, Contact
from crm.models.opportunity_model import Opportunity, Pipeline
from crm.models.activity_model import Activity
from crm.models.campaign_model import Campaign
from crm.models.ticket_model import Ticket
from crm.models.analytics_model import Report
from crm.services.analytics_service import AnalyticsService

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Export CRM data with advanced filtering and multiple format support'

    def add_arguments(self, parser):
        # Export type and format
        parser.add_argument(
            '--type',
            choices=['leads', 'accounts', 'opportunities', 'activities', 'campaigns', 
                    'tickets', 'analytics', 'all', 'custom'],
            help='Type of data to export',
            default='leads'
        )
        
        parser.add_argument(
            '--format',
            choices=['csv', 'json', 'xlsx', 'xml', 'html'],
            help='Export format',
            default='csv'
        )
        
        parser.add_argument(
            '--output',
            type=str,
            help='Output file path',
            default=None
        )
        
        # Filtering options
        parser.add_argument(
            '--date-from',
            type=str,
            help='Start date for filtering (YYYY-MM-DD)',
            default=None
        )
        
        parser.add_argument(
            '--date-to',
            type=str,
            help='End date for filtering (YYYY-MM-DD)',
            default=None
        )
        
        parser.add_argument(
            '--status',
            type=str,
            help='Filter by status',
            default=None
        )
        
        parser.add_argument(
            '--owner',
            type=str,
            help='Filter by owner email',
            default=None
        )
        
        parser.add_argument(
            '--source',
            type=str,
            help='Filter by lead source',
            default=None
        )
        
        parser.add_argument(
            '--include-related',
            action='store_true',
            help='Include related objects in export',
        )
        
        # Advanced options
        parser.add_argument(
            '--query',
            type=str,
            help='Custom query filters as JSON',
            default=None
        )
        
        parser.add_argument(
            '--fields',
            type=str,
            help='Comma-separated list of fields to export',
            default=None
        )
        
        parser.add_argument(
            '--limit',
            type=int,
            help='Maximum number of records to export',
            default=None
        )
        
        parser.add_argument(
            '--compress',
            action='store_true',
            help='Compress output file',
        )
        
        parser.add_argument(
            '--scheduled',
            action='store_true',
            help='Mark as scheduled export (affects file naming)',
        )
        
        parser.add_argument(
            '--email-to',
            type=str,
            help='Email address to send export to',
            default=None
        )

    def handle(self, *args, **options):
        try:
            self.analytics_service = AnalyticsService()
            self.export_data(**options)
            
        except Exception as e:
            logger.error(f"Data export failed: {str(e)}")
            raise CommandError(f'Data export failed: {str(e)}')

    def export_data(self, **options):
        """Main export orchestrator"""
        export_type = options['type']
        
        self.stdout.write(f'📤 Starting {export_type} export in {options["format"]} format...')
        
        # Validate format requirements
        if options['format'] == 'xlsx' and not EXCEL_AVAILABLE:
            raise CommandError('xlsxwriter package required for Excel export. Install with: pip install xlsxwriter')
        
        # Parse date filters
        date_filters = self._parse_date_filters(options)
        
        # Get data based on export type
        if export_type == 'all':
            data = self._export_all_data(date_filters, options)
        elif export_type == 'custom':
            data = self._export_custom_query(options)
        else:
            data = self._export_single_type(export_type, date_filters, options)
        
        # Generate output file path
        output_path = self._generate_output_path(export_type, options)
        
        # Export data in requested format
        exported_file = self._export_to_format(data, output_path, options)
        
        # Compress if requested
        if options['compress']:
            exported_file = self._compress_file(exported_file)
        
        # Email if requested
        if options['email_to']:
            self._email_export(exported_file, options)
        
        # Print summary
        self._print_export_summary(data, exported_file, options)

    def _parse_date_filters(self, options: Dict) -> Dict:
        """Parse date filter options"""
        date_filters = {}
        
        if options['date_from']:
            try:
                date_filters['from'] = datetime.strptime(options['date_from'], '%Y-%m-%d').date()
            except ValueError:
                raise CommandError('Invalid date-from format. Use YYYY-MM-DD')
        
        if options['date_to']:
            try:
                date_filters['to'] = datetime.strptime(options['date_to'], '%Y-%m-%d').date()
            except ValueError:
                raise CommandError('Invalid date-to format. Use YYYY-MM-DD')
        
        return date_filters

    def _export_single_type(self, export_type: str, date_filters: Dict, options: Dict) -> Dict:
        """Export single data type"""
        exporters = {
            'leads': self._export_leads,
            'accounts': self._export_accounts,
            'opportunities': self._export_opportunities,
            'activities': self._export_activities,
            'campaigns': self._export_campaigns,
            'tickets': self._export_tickets,
            'analytics': self._export_analytics,
        }
        
        exporter = exporters.get(export_type)
        if not exporter:
            raise CommandError(f'Unknown export type: {export_type}')
        
        return exporter(date_filters, options)

    def _export_leads(self, date_filters: Dict, options: Dict) -> Dict:
        """Export leads with comprehensive data"""
        queryset = Lead.objects.select_related('source', 'assigned_to__user').all()
        
        # Apply filters
        queryset = self._apply_date_filter(queryset, date_filters, 'created_at')
        queryset = self._apply_common_filters(queryset, options)
        
        if options['source']:
            queryset = queryset.filter(source__name__icontains=options['source'])
        
        # Get related data if requested
        related_data = {}
        if options['include_related']:
            related_data = {
                'lead_sources': list(LeadSource.objects.values()),
                'activities': self._get_related_activities(queryset, 'lead'),
            }
        
        # Convert to dict format
        leads_data = []
        for lead in queryset:
            lead_dict = {
                'id': lead.id,
                'full_name': f"{lead.first_name} {lead.last_name}",
                'first_name': lead.first_name,
                'last_name': lead.last_name,
                'email': lead.email,
                'phone': lead.phone,
                'company': lead.company,
                'job_title': lead.job_title,
                'industry': lead.industry,
                'status': lead.status,
                'score': float(lead.score) if lead.score else 0,
                'source': lead.source.name if lead.source else '',
                'assigned_to': lead.assigned_to.user.email if lead.assigned_to else '',
                'budget': float(lead.budget) if lead.budget else 0,
                'website': lead.website,
                'notes': lead.notes,
                'created_at': lead.created_at.isoformat(),
                'updated_at': lead.updated_at.isoformat(),
                'last_activity_date': lead.last_activity_date.isoformat() if lead.last_activity_date else '',
            }
            
            # Add address fields
            lead_dict.update({
                'address': lead.address,
                'city': lead.city,
                'state': lead.state,
                'country': lead.country,
                'postal_code': lead.postal_code,
            })
            
            leads_data.append(lead_dict)
        
        return {
            'type': 'leads',
            'count': len(leads_data),
            'data': leads_data,
            'related': related_data,
            'filters_applied': self._get_filters_summary(options, date_filters),
        }

    def _export_accounts(self, date_filters: Dict, options: Dict) -> Dict:
        """Export accounts with contacts and opportunities"""
        queryset = Account.objects.select_related('industry', 'assigned_to__user').prefetch_related('contacts').all()
        
        queryset = self._apply_date_filter(queryset, date_filters, 'created_at')
        queryset = self._apply_common_filters(queryset, options, status_field='account_status')
        
        accounts_data = []
        for account in queryset:
            # Get account metrics
            opportunities_count = account.opportunities.count()
            total_revenue = account.opportunities.filter(stage__stage_type='WON').aggregate(
                total=Sum('value')
            )['total'] or 0
            
            account_dict = {
                'id': account.id,
                'name': account.name,
                'industry': account.industry.name if account.industry else '',
                'account_type': account.account_type,
                'account_status': account.account_status,
                'website': account.website,
                'phone': account.phone,
                'email': account.email,
                'annual_revenue': float(account.annual_revenue) if account.annual_revenue else 0,
                'employee_count': account.employee_count,
                'assigned_to': account.assigned_to.user.email if account.assigned_to else '',
                'health_score': float(account.health_score) if account.health_score else 0,
                'opportunities_count': opportunities_count,
                'total_revenue': float(total_revenue),
                'contacts_count': account.contacts.count(),
                'created_at': account.created_at.isoformat(),
                'updated_at': account.updated_at.isoformat(),
            }
            
            # Add contacts if requested
            if options['include_related']:
                account_dict['contacts'] = [
                    {
                        'name': f"{contact.first_name} {contact.last_name}",
                        'email': contact.email,
                        'phone': contact.phone,
                        'job_title': contact.job_title,
                        'is_primary': contact.is_primary,
                    }
                    for contact in account.contacts.all()
                ]
            
            accounts_data.append(account_dict)
        
        return {
            'type': 'accounts',
            'count': len(accounts_data),
            'data': accounts_data,
            'filters_applied': self._get_filters_summary(options, date_filters),
        }

    def _export_opportunities(self, date_filters: Dict, options: Dict) -> Dict:
        """Export opportunities with pipeline data"""
        queryset = Opportunity.objects.select_related(
            'account', 'pipeline', 'stage', 'assigned_to__user'
        ).prefetch_related('products').all()
        
        queryset = self._apply_date_filter(queryset, date_filters, 'created_at')
        queryset = self._apply_common_filters(queryset, options, status_field='stage__stage_type')
        
        opportunities_data = []
        for opp in queryset:
            opp_dict = {
                'id': opp.id,
                'name': opp.name,
                'account': opp.account.name if opp.account else '',
                'value': float(opp.value) if opp.value else 0,
                'pipeline': opp.pipeline.name if opp.pipeline else '',
                'stage': opp.stage.name if opp.stage else '',
                'stage_type': opp.stage.stage_type if opp.stage else '',
                'probability': opp.stage.probability if opp.stage else 0,
                'expected_close_date': opp.expected_close_date.isoformat() if opp.expected_close_date else '',
                'actual_close_date': opp.actual_close_date.isoformat() if opp.actual_close_date else '',
                'assigned_to': opp.assigned_to.user.email if opp.assigned_to else '',
                'source': opp.source,
                'description': opp.description,
                'created_at': opp.created_at.isoformat(),
                'updated_at': opp.updated_at.isoformat(),
            }
            
            # Add products if requested
            if options['include_related']:
                opp_dict['products'] = [
                    {
                        'name': op.product.name,
                        'quantity': op.quantity,
                        'unit_price': float(op.unit_price),
                        'total': float(op.total_price),
                    }
                    for op in opp.products.all()
                ]
            
            opportunities_data.append(opp_dict)
        
        return {
            'type': 'opportunities',
            'count': len(opportunities_data),
            'data': opportunities_data,
            'filters_applied': self._get_filters_summary(options, date_filters),
        }

    def _export_activities(self, date_filters: Dict, options: Dict) -> Dict:
        """Export activities with comprehensive details"""
        queryset = Activity.objects.select_related(
            'activity_type', 'assigned_to__user', 'created_by__user'
        ).all()
        
        queryset = self._apply_date_filter(queryset, date_filters, 'scheduled_at')
        queryset = self._apply_common_filters(queryset, options)
        
        activities_data = []
        for activity in queryset:
            activity_dict = {
                'id': activity.id,
                'subject': activity.subject,
                'activity_type': activity.activity_type.name if activity.activity_type else '',
                'status': activity.status,
                'priority': activity.priority,
                'assigned_to': activity.assigned_to.user.email if activity.assigned_to else '',
                'created_by': activity.created_by.user.email if activity.created_by else '',
                'scheduled_at': activity.scheduled_at.isoformat() if activity.scheduled_at else '',
                'completed_at': activity.completed_at.isoformat() if activity.completed_at else '',
                'duration_minutes': activity.duration_minutes,
                'description': activity.description,
                'outcome': activity.outcome,
                'created_at': activity.created_at.isoformat(),
                'updated_at': activity.updated_at.isoformat(),
            }
            
            # Add related object info
            if activity.related_lead:
                activity_dict['related_lead'] = activity.related_lead.email
            if activity.related_account:
                activity_dict['related_account'] = activity.related_account.name
            if activity.related_opportunity:
                activity_dict['related_opportunity'] = activity.related_opportunity.name
            
            activities_data.append(activity_dict)
        
        return {
            'type': 'activities',
            'count': len(activities_data),
            'data': activities_data,
            'filters_applied': self._get_filters_summary(options, date_filters),
        }

    def _export_campaigns(self, date_filters: Dict, options: Dict) -> Dict:
        """Export campaigns with performance metrics"""
        queryset = Campaign.objects.select_related('campaign_type', 'owner__user').all()
        
        queryset = self._apply_date_filter(queryset, date_filters, 'start_date')
        queryset = self._apply_common_filters(queryset, options)
        
        campaigns_data = []
        for campaign in queryset:
            # Calculate performance metrics
            members_count = campaign.members.count()
            responded_count = campaign.members.filter(status='RESPONDED').count()
            converted_count = campaign.members.filter(status='CONVERTED').count()
            
            response_rate = (responded_count / members_count * 100) if members_count > 0 else 0
            conversion_rate = (converted_count / members_count * 100) if members_count > 0 else 0
            roi = self._calculate_campaign_roi(campaign)
            
            campaign_dict = {
                'id': campaign.id,
                'name': campaign.name,
                'campaign_type': campaign.campaign_type.name if campaign.campaign_type else '',
                'status': campaign.status,
                'owner': campaign.owner.user.email if campaign.owner else '',
                'start_date': campaign.start_date.isoformat() if campaign.start_date else '',
                'end_date': campaign.end_date.isoformat() if campaign.end_date else '',
                'budget': float(campaign.budget) if campaign.budget else 0,
                'actual_cost': float(campaign.actual_cost) if campaign.actual_cost else 0,
                'expected_revenue': float(campaign.expected_revenue) if campaign.expected_revenue else 0,
                'members_count': members_count,
                'responded_count': responded_count,
                'converted_count': converted_count,
                'response_rate': round(response_rate, 2),
                'conversion_rate': round(conversion_rate, 2),
                'roi': round(roi, 2),
                'description': campaign.description,
                'created_at': campaign.created_at.isoformat(),
                'updated_at': campaign.updated_at.isoformat(),
            }
            
            campaigns_data.append(campaign_dict)
        
        return {
            'type': 'campaigns',
            'count': len(campaigns_data),
            'data': campaigns_data,
            'filters_applied': self._get_filters_summary(options, date_filters),
        }

    def _export_tickets(self, date_filters: Dict, options: Dict) -> Dict:
        """Export support tickets with SLA metrics"""
        queryset = Ticket.objects.select_related(
            'category', 'sla', 'assigned_to__user', 'created_by__user'
        ).all()
        
        queryset = self._apply_date_filter(queryset, date_filters, 'created_at')
        queryset = self._apply_common_filters(queryset, options)
        
        tickets_data = []
        for ticket in queryset:
            # Calculate SLA metrics
            response_time = self._calculate_response_time(ticket)
            resolution_time = self._calculate_resolution_time(ticket)
            sla_status = self._get_sla_status(ticket, response_time, resolution_time)
            
            ticket_dict = {
                'id': ticket.id,
                'subject': ticket.subject,
                'status': ticket.status,
                'priority': ticket.priority,
                'category': ticket.category.name if ticket.category else '',
                'sla': ticket.sla.name if ticket.sla else '',
                'assigned_to': ticket.assigned_to.user.email if ticket.assigned_to else '',
                'created_by': ticket.created_by.user.email if ticket.created_by else '',
                'created_at': ticket.created_at.isoformat(),
                'first_response_at': ticket.first_response_at.isoformat() if ticket.first_response_at else '',
                'resolved_at': ticket.resolved_at.isoformat() if ticket.resolved_at else '',
                'closed_at': ticket.closed_at.isoformat() if ticket.closed_at else '',
                'response_time_hours': response_time,
                'resolution_time_hours': resolution_time,
                'sla_status': sla_status,
                'customer_satisfaction': ticket.customer_satisfaction,
                'description': ticket.description,
                'resolution_notes': ticket.resolution_notes,
                'updated_at': ticket.updated_at.isoformat(),
            }
            
            # Add customer info
            if ticket.contact:
                ticket_dict.update({
                    'customer_name': f"{ticket.contact.first_name} {ticket.contact.last_name}",
                    'customer_email': ticket.contact.email,
                    'customer_company': ticket.contact.account.name if ticket.contact.account else '',
                })
            
            tickets_data.append(ticket_dict)
        
        return {
            'type': 'tickets',
            'count': len(tickets_data),
            'data': tickets_data,
            'filters_applied': self._get_filters_summary(options, date_filters),
        }

    def _export_analytics(self, date_filters: Dict, options: Dict) -> Dict:
        """Export analytics and reports data"""
        # Get various analytics metrics
        analytics_data = {
            'summary': self._get_analytics_summary(date_filters),
            'lead_metrics': self._get_lead_analytics(date_filters),
            'sales_metrics': self._get_sales_analytics(date_filters),
            'activity_metrics': self._get_activity_analytics(date_filters),
            'campaign_metrics': self._get_campaign_analytics(date_filters),
            'support_metrics': self._get_support_analytics(date_filters),
        }
        
        return {
            'type': 'analytics',
            'count': len(analytics_data),
            'data': analytics_data,
            'filters_applied': self._get_filters_summary(options, date_filters),
        }

    def _export_all_data(self, date_filters: Dict, options: Dict) -> Dict:
        """Export all data types"""
        all_data = {}
        
        export_types = ['leads', 'accounts', 'opportunities', 'activities', 'campaigns', 'tickets']
        
        for export_type in export_types:
            self.stdout.write(f'  📋 Exporting {export_type}...')
            try:
                type_data = self._export_single_type(export_type, date_filters, options)
                all_data[export_type] = type_data
            except Exception as e:
                logger.warning(f"Failed to export {export_type}: {str(e)}")
                all_data[export_type] = {'error': str(e)}
        
        # Add analytics summary
        all_data['analytics'] = self._export_analytics(date_filters, options)
        
        return {
            'type': 'all',
            'count': sum(data.get('count', 0) for data in all_data.values() if isinstance(data, dict)),
            'data': all_data,
            'filters_applied': self._get_filters_summary(options, date_filters),
        }

    def _export_custom_query(self, options: Dict) -> Dict:
        """Export based on custom query"""
        if not options['query']:
            raise CommandError('Custom export requires --query parameter with JSON filters')
        
        try:
            query_config = json.loads(options['query'])
        except json.JSONDecodeError:
            raise CommandError('Invalid JSON in query parameter')
        
        model_name = query_config.get('model')
        if not model_name:
            raise CommandError('Custom query must specify "model" parameter')
        
        # Get model class
        try:
            model_class = apps.get_model('crm', model_name)
        except LookupError:
            raise CommandError(f'Model not found: {model_name}')
        
        # Build queryset
        queryset = model_class.objects.all()
        
        # Apply custom filters
        filters = query_config.get('filters', {})
        if filters:
            queryset = queryset.filter(**filters)
        
        # Apply ordering
        ordering = query_config.get('ordering')
        if ordering:
            queryset = queryset.order_by(*ordering if isinstance(ordering, list) else [ordering])
        
        # Convert to dict
        data = list(queryset.values())
        
        return {
            'type': 'custom',
            'count': len(data),
            'data': data,
            'query': query_config,
        }

    def _apply_date_filter(self, queryset, date_filters: Dict, date_field: str = 'created_at'):
        """Apply date range filters to queryset"""
        if date_filters.get('from'):
            queryset = queryset.filter(**{f'{date_field}__gte': date_filters['from']})
        
        if date_filters.get('to'):
            # Add one day to include the entire end date
            end_date = date_filters['to'] + timedelta(days=1)
            queryset = queryset.filter(**{f'{date_field}__lt': end_date})
        
        return queryset

    def _apply_common_filters(self, queryset, options: Dict, status_field: str = 'status'):
        """Apply common filters like status, owner, etc."""
        if options['status']:
            queryset = queryset.filter(**{status_field: options['status']})
        
        if options['owner']:
            queryset = queryset.filter(assigned_to__user__email=options['owner'])
        
        if options['limit']:
            queryset = queryset[:options['limit']]
        
        return queryset

    def _generate_output_path(self, export_type: str, options: Dict) -> str:
        """Generate output file path"""
        if options['output']:
            return options['output']
        
        # Generate filename with timestamp
        timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')
        
        if options['scheduled']:
            filename = f"scheduled_{export_type}_export_{timestamp}"
        else:
            filename = f"{export_type}_export_{timestamp}"
        
        extension = options['format']
        if extension == 'xlsx':
            extension = 'xlsx'
        
        return f"{filename}.{extension}"

    def _export_to_format(self, data: Dict, output_path: str, options: Dict) -> str:
        """Export data in requested format"""
        format_type = options['format']
        
        if format_type == 'csv':
            return self._export_to_csv(data, output_path, options)
        elif format_type == 'json':
            return self._export_to_json(data, output_path, options)
        elif format_type == 'xlsx':
            return self._export_to_excel(data, output_path, options)
        elif format_type == 'xml':
            return self._export_to_xml(data, output_path, options)
        elif format_type == 'html':
            return self._export_to_html(data, output_path, options)
        else:
            raise CommandError(f'Unsupported export format: {format_type}')

    def _export_to_ output_path: str, options: Dict) -> str:
        """Export to CSV format"""
        with open(output_path, 'w', newline='', encoding='utf-8') as csvfile:
            if data['type'] == 'all':
                # Multiple sheets approach - create separate files
                base_path = output_path.rsplit('.', 1)[0]
                files_created = []
                
                for data_type, type_data in data['data'].items():
                    if isinstance(type_data, dict) and 'data        type_file = f"{base_path}_{data_type}.csv"
                        self._write_csv_data(type_data['data'], type_file)
                        files_created.append(type_file)
                
                # Create a zip file containing all CSV files
                zip_path = f"{base_path}_all.zip"
                with zipfile.ZipFile(zip_path, 'w') as zipf:
                    for file_path in files_created:
                        zipf.write(file_path, os.path.basename(file_path))
                        os.remove(file_path)  # Clean up individual files
                
                return zip_path
            else:
                # Single data type
                self._write_csv_data(data['data'], output_path)
                return output_path

    def _write_csv_data(self, records: List[Dict], file_path: str):
        """Write records to CSV file"""
        if not records:
            return
        
        with open(file_path, 'w', newline='', encoding='utf-8') as csvfile:
            # Get all possible fieldnames from all records
            fieldnames = set()
            for record in records:
                if isinstance(record, dict):
                    fieldnames.update(record.keys())
            
            fieldnames = sorted(list(fieldnames))
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            
            writer.writeheader()
            for record in records:
                if isinstance(record, dict):
                    # Handle nested objects by converting to string
                    clean_record = {}
                    for key, value in record.items():
                        if isinstance(value, (list, dict)):
                            clean_record[key] = json.dumps(value)
                        else:
                            clean_record[key] = value
                    writer.writerow(clean_record)

    def _export_to_json_path: str, options: Dict) -> str:
        """Export to JSON format"""
        # Convert Decimal objects to float for JSON serialization
        def decimal_default(obj):
            if isinstance(obj, Decimal):
                return float(obj)
            raise TypeError
        
        with open(output_path, 'w', encoding='utf-8') as jsonfile:
            json.dump(data, jsonfile, indent=2, default=decimal_default, ensure_ascii=False)
        
        return output_path

    def _export_to_excel( -> str:
        """Export to Excel format with multiple sheets"""
        workbook = xlsxwriter.Workbook(output_path)
        
        # Add formats
        header_format = workbook.add_format({
            'bold': True,
            'bg_color': '#D7E4BD',
            'border': 1
        })
        
        if data['type'] == 'all':
            # Create sheets for each data type
            for data_type, type_data in data['data'].items():
                if isinstance(type_data, dict) and 'data' in type_data and type_data['data']:
                    worksheet = workbook.add_worksheet(data_type.title())
                    self._write_excel_data(worksheet, type_data['data'], header_format)
        else:
            # Single sheet
            worksheet = workbook.add_worksheet(data['type'].title())
            if data['data']:
                self._write_excel_data(worksheet, data['data'], header_format)
        
        # Add summary sheet
        summary_sheet = workbook.add_worksheet('Export Summary')
        self._write_export_summary_sheet(summary_sheet, data, header_format)
        
        workbook.close()
        return output_path

    def _write_excel_data(self, worksheet, records: List[Dict], header_format):
        """Write records to Excel worksheet"""
        if not records:
            return
        
        # Get headers
        headers = list(records[0].keys()) if records else []
        
        # Write headers
        for col, header in enumerate(headers):
            worksheet.write(0, col, header.replace('_', ' ').title(), header_format)
        
        # Write data
        for row, record in enumerate(records, 1):
            for col, header in enumerate(headers):
                value = record.get(header, '')
                
                # Handle different data types
                if isinstance(value, (list, dict)):
                    value = json.dumps(value)
                elif isinstance(value, Decimal):
                    value = float(value)
                
                worksheet.write(row, col, value)

    def _write_export_summary_sheet(self_format):
        """Write export summary to Excel sheet"""
        worksheet.write(0, 0, 'Export Summary', header_format)
        
        row = 2
        worksheet.write(row, 0, 'Export Type:', header_format)
        worksheet.write(row, 1, data['type'])
        
        row += 1
        worksheet.write(row, 0, 'Total Records:', header_format)
        worksheet.write(row, 1, data['count'])
        
        row += 1
        worksheet.write(row, 0, 'Export Date:', header_format)
        worksheet.write(row, 1, timezone.now().strftime('%Y-%m-%d %H:%M:%S'))
        
        # Add filters applied
        if 
            row += 2
            worksheet.write(row, 0, 'Filters Applied:', header_format)
            row += 1
            for filter_name, filter_value in data['filters_applied'].items():
                worksheet.write(row, 0, f'{filter_name}:')
                worksheet.write(row, 1, str(filter_value))
                row += 1

    def _export_to_xml(self, str, options: Dict) -> str:
        """Export to XML format"""
        # Use Django's serialization for XML
        with open(output_path, 'w', encoding='utf-8') as xmlfile:
            xmlfile.write('<?xml version="1.0" encoding="UTF-8"?>\n')
            xmlfile.write(f'<crm_export type="{data["type"]}" count="{data["count"]}">\n')
            
            if data['type'] == 'all':
                for data_type, type_data in data['data'].items():
                    if isinstance(type_data, dict) and 'data' infile.write(f'  <{data_type}>\n')
                        for record in type_data['data']:
                            self._write_xml_record(xmlfile, record, 4)
                        xmlfile.write(f'  </{data_type}>\n')
            else:
                for record in data['data']:
                    self._write_xml_record(xmlfile, record, 2)
            
            xmlfile.write('</crm_export>\n')
        
        return output_path

    def _write_xml_record(self, file, record: Dict, indent: int):
        """Write a single record to XML"""
        spaces = ' ' * indent
        file.write(f'{spaces}<record>\n')
        
        for key, value in record.items():
            clean_key = key.replace(' ', '_').lower()
            if isinstance(value, (list, dict)):
                value = json.dumps(value)
            elif value is None:
                value = ''
            
            file.write(f'{spaces}  <{clean_key}>{value}</{clean_key}>\n')
        
        file.write(f'{spaces}</record>\n')

    def _export_to_html(self, str, options: Dict) -> str:
        """Export to HTML format with nice formatting"""
        html_content = render_to_string('crm/exports/data_export.html', {
            'data': data,
            'export_date': timezone.now(),
            'options': options,
        })
        
        with open(output_path, 'w', encoding='utf-8') as htmlfile:
            htmlfile.write(html_content)
        
        return output_path

    # Helper methods for analytics calculations
    def _calculate_campaign_roi(self, campaign) -> float:
        """Calculate campaign ROI"""
        if not campaign.actual_cost or campaign.actual_cost == 0:
            return 0
        
        # Get revenue from converted members
        revenue = campaign.members.filter(
            status='CONVERTED'
        ).aggregate(
            total=Sum('converted_opportunity__value')
        )['total'] or 0
        
        if revenue == 0:
            return -100  # Complete loss
        
        roi = ((revenue - campaign.actual_cost) / campaign.actual_cost) * 100
        return roi

    def _calculate_response_time(self, ticket) -> Optional[float]:
        """Calculate ticket response time in hours"""
        if not ticket.first_response_at:
            return None
        
        delta = ticket.first_response_at - ticket.created_at
        return delta.total_seconds() / 3600

    def _calculate_resolution_time(self, ticket) -> Optional[float]:
        """Calculate ticket resolution time in hours"""
        if not ticket.resolved_at:
            return None
        
        delta = ticket.resolved_at - ticket.created_at
        return delta.total_seconds() / 3600

    def _get_sla_status(self, ticket, response_time: Optional[float], resolution_time: Optional[float]) -> str:
        """Get SLA compliance status"""
        if not ticket.sla:
            return 'No SLA'
        
        sla_breached = False
        
        # Check response time SLA
        if response_time is not None:
            if response_time > ticket.sla.response_time_hours:
                sla_breached = True
        
        # Check resolution time SLA
        if resolution_time is not None:
            if resolution_time > ticket.sla.resolution_time_hours:
                sla_breached = True
        
        return 'Breached' if sla_breached else 'Met'

    def _get_analytics_summary(self, date_filters: Dict) -> Dict:
        """Get overall analytics summary"""
        return self.analytics_service.get_dashboard_data(
            date_from=date_filters.get('from'),
            date_to=date_filters.get('to')
        )

    def _get_lead_analytics(self, date_filters: Dict) -> Dict:
        """Get lead-specific analytics"""
        queryset = Lead.objects.all()
        queryset = self._apply_date_filter(queryset, date_filters, 'created_at')
        
        return {
            'total_leads': queryset.count(),
            'by_status': dict(queryset.values_list('status').annotate(count=Count('id'))),
            'by_source': dict(queryset.values_list('source__name').annotate(count=Count('id'))),
            'average_score': queryset.aggregate(avg=Avg('score'))['avg'] or 0,
            'conversion_rate': self._calculate_lead_conversion_rate(queryset),
        }

    def _get_sales_analytics(self, date_filters: Dict) -> Dict:
        """Get sales-specific analytics"""
        queryset = Opportunity.objects.all()
        queryset = self._apply_date_filter(queryset, date_filters, 'created_at')
        
        return {
            'total_opportunities': queryset.count(),
            'total_value': queryset.aggregate(total=Sum('value'))['total'] or 0,
            'won_deals': queryset.filter(stage__stage_type='WON').count(),
            'won_value': queryset.filter(stage__stage_type='WON').aggregate(total=Sum('value'))['total'] or 0,
            'average_deal_size': queryset.aggregate(avg=Avg('value'))['avg'] or 0,
            'win_rate': self._calculate_win_rate(queryset),
        }

    def _get_activity_analytics(self, date_filters: Dict) -> Dict:
        """Get activity analytics"""
        queryset = Activity.objects.all()
        queryset = self._apply_date_filter(queryset, date_filters, 'scheduled_at')
        
        return {
            'total_activities': queryset.count(),
            'completed_activities': queryset.filter(status='COMPLETED').count(),
            'by_type': dict(queryset.values_list('activity_type__name').annotate(count=Count('id'))),
            'completion_rate': self._calculate_activity_completion_rate(queryset),
        }

    def _get_campaign_analytics(self, date_filters: Dict) -> Dict:
        """Get campaign analytics"""
        queryset = Campaign.objects.all()
        queryset = self._apply_date_filter(queryset, date_filters, 'start_date')
        
        total_budget = queryset.aggregate(total=Sum('budget'))['total'] or 0
        total_cost = queryset.aggregate(total=Sum('actual_cost'))['total'] or 0
        
        return {
            'total_campaigns': queryset.count(),
            'total_budget': total_budget,
            'total_cost': total_cost,
            'budget_utilization': (total_cost / total_budget * 100) if total_budget > 0 else 0,
            'active_campaigns': queryset.filter(status='ACTIVE').count(),
        }

    def _get_support_analytics(self, date_filters: Dict) -> Dict:
        """Get support ticket analytics"""
        queryset = Ticket.objects.all()
        queryset = self._apply_date_filter(queryset, date_filters, 'created_at')
        
        return {
            'total_tickets': queryset.count(),
            'open_tickets': queryset.exclude(status='CLOSED').count(),
            'closed_tickets': queryset.filter(status='CLOSED').count(),
            'by_priority': dict(queryset.values_list('priority').annotate(count=Count('id'))),
            'by_category': dict(queryset.values_list('category__name').annotate(count=Count('id'))),
            'average_satisfaction': queryset.filter(
                customer_satisfaction__isnull=False
            ).aggregate(avg=Avg('customer_satisfaction'))['avg'] or 0,
        }

    def _calculate_lead_conversion_rate(self, queryset) -> float:
        """Calculate lead conversion rate"""
        total = queryset.count()
        if total == 0:
            return 0
        
        converted = queryset.filter(status='CONVERTED').count()
        return (converted / total) * 100

    def _calculate_win_rate(self, queryset) -> float:
        """Calculate opportunity win rate"""
        closed = queryset.filter(stage__stage_type__in=['WON', 'LOST']).count()
        if closed == 0:
            return 0
        
        won = queryset.filter(stage__stage_type='WON').count()
        return (won / closed) * 100

    def _calculate_activity_completion_rate(self, queryset) -> float:
        """Calculate activity completion rate"""
        total = queryset.count()
        if total == 0:
            return 0
        
        completed = queryset.filter(status='COMPLETED').count()
        return (completed / total) * 100

    def _get_related_activities(self, parent_queryset, parent_type: str) -> List[Dict]:
        """Get activities related to parent objects"""
        if parent_type == 'lead':
            activities = Activity.objects.filter(
                related_lead__in=parent_queryset
            ).select_related('activity_type')
        else:
            return []
        
        return [
            {
                'subject': activity.subject,
                'type': activity.activity_type.name if activity.activity_type else '',
                'status': activity.status,
                'scheduled_at': activity.scheduled_at.isoformat() if activity.scheduled_at else '',
            }
            for activity in activities[:100]  # Limit for performance
        ]

    def _get_filters_summary(self, options: Dict, date_filters: Dict) -> Dict:
        """Get summary of applied filters"""
        filters = {}
        
        if date_filters.get('from'):
            filters['date_from'] = date_filters['from'].isoformat()
        if date_filters.get('to'):
            filters['date_to'] = date_filters['to'].isoformat()
        if options['status']:
            filters['status'] = options['status']
        if options['owner']:
            filters['owner'] = options['owner']
        if options['source']:
            filters['source'] = options['source']
        if options['limit']:
            filters['limit'] = options['limit']
        
        return filters

    def _compress_file(self, file_path: str) -> str:
        """Compress the exported file"""
        zip_path = f"{file_path}.zip"
        
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            zipf.write(file_path, os.path.basename(file_path))
        
        # Remove original file
        os.remove(file_path)
        
        return zip_path

    def _email_export(self, file_path: str, options: Dict):
        """Email the export file"""
        from django.core.mail import EmailMessage
        
        subject = f'CRM Data Export - {options["type"].title()}'
        body = f"""
        Your CRM data export is ready.
        
        Export Details:
        - Type: {options["type"]}
        - Format: {options["format"]}
        - Generated: {timezone.now().strftime('%Y-%m-%d %H:%M:%S')}
        - File: {os.path.basename(file_path)}
        
        Please find the export attached.
        """
        
        email = EmailMessage(
            subject=subject,
            body=body,
            to=[options['email_to']]
        )
        
        email.attach_file(file_path)
        email.send()
        
        self.stdout.write(f'✉️ Export emailed to: {options["email_to"]}')

    def _print_export_summary(self, data: Dict, file_path: str, options: Dict):
        """Print export completion summary"""
        self.stdout.write('\n' + '='*60)
        self.stdout.write('📊 EXPORT SUMMARY')
        self.stdout.write('='*60)
        self.stdout.write(f'Export Type: {data["type"].title()}')
        self.stdout.write(f'Format: {options["format"].upper()}')
        self.stdout.write(f'Records: {data["count"]:,}')
        self.stdout.write(f'File: {file_path}')
        self.stdout.write(f'Size: {self._get_file_size(file_path)}')
        
        if 'filters_applied' in data and data['filters_applied']:
            self.stdout.write('\nFilters Applied:')
            for filter_name, filter_value in data['filters_applied'].items():
                self.stdout.write(f'  {filter_name}: {filter_value}')
        
        self.stdout.write('='*60)
        self.stdout.write(
            self.style.SUCCESS(f'✅ Export completed successfully!')
        )

    def _get_file_size(self, file_path: str) -> str:
        """Get human-readable file size"""
        size = os.path.getsize(file_path)
        
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        
        return f"{size:.1f} TB"