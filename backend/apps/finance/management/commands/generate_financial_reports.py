# backend/apps/finance/management/commands/generate_financial_reports.py

"""
Generate Financial Reports
"""

from django.core.management.base import BaseCommand, CommandError
from apps.core.models import Tenant
from apps.finance.services.reporting import FinancialReportingService
from datetime import date, datetime
import os


class Command(BaseCommand):
    """Generate financial reports"""
    
    help = 'Generate financial reports for a tenant'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--tenant',
            type=str,
            required=True,
            help='Tenant schema name'
        )
        parser.add_argument(
            '--report-type',
            type=str,
            required=True,
            choices=[
                'trial_balance', 'balance_sheet', 'income_statement',
                'cash_flow', 'ar_aging', 'ap_aging'
            ],
            help='Type of report to generate'
        )
        parser.add_argument(
            '--as-of-date',
            type=str,
            help='As of date for balance sheet (YYYY-MM-DD)'
        )
        parser.add_argument(
            '--start-date',
            type=str,
            help='Start date for period reports (YYYY-MM-DD)'
        )
        parser.add_argument(
            '--end-date',
            type=str,
            help='End date for period reports (YYYY-MM-DD)'
        )
        parser.add_argument(
            '--output-format',
            type=str,
            default='json',
            choices=['json', 'csv', 'pdf'],
            help='Output format'
        )
        parser.add_argument(
            '--output-file',
            type=str,
            help='Output file path'
        )

    def handle(self, *args, **options):
        try:
            tenant = Tenant.objects.get(schema_name=options['tenant'])
        except Tenant.DoesNotExist:
            raise CommandError(f"Tenant '{options['tenant']}' does not exist")
        
        service = FinancialReportingService(tenant)
        report_type = options['report_type']
        
        # Parse dates
        as_of_date = None
        start_date = None
        end_date = None
        
        if options['as_of_date']:
            as_of_date = datetime.strptime(options['as_of_date'], '%Y-%m-%d').date()
        
        if options['start_date']:
            start_date = datetime.strptime(options['start_date'], '%Y-%m-%d').date()
        
        if options['end_date']:
            end_date = datetime.strptime(options['end_date'], '%Y-%m-%d').date()
        
        # Generate report
        try:
            if report_type == 'trial_balance':
                report_data = service.generate_trial_balance(as_of_date or date.today())
            elif report_type == 'balance_sheet':
                report_data = service.generate_balance_sheet(as_of_date or date.today())
            elif report_type == 'income_statement':
                report_data = service.generate_income_statement(
                    start_date or date.today().replace(day=1),
                    end_date or date.today()
                )
            elif report_type == 'cash_flow':
                report_data = service.generate_cash_flow_statement(
                    start_date or date.today().replace(day=1),
                    end_date or date.today()
                )
            elif report_type == 'ar_aging':
                report_data = service.generate_ar_aging_report(as_of_date or date.today())
            elif report_type == 'ap_aging':
                report_data = service.generate_ap_aging_report(as_of_date or date.today())
            
            # Output report
            if options['output_file']:
                output_path = options['output_file']
            else:
                output_path = f"{report_type}_{tenant.schema_name}_{date.today()}.{options['output_format']}"
            
            if options['output_format'] == 'json':
                import json
                with open(output_path, 'w') as f:
                    json.dump(report_data, f, indent=2, default=str)
            elif options['output_format'] == 'csv':
                service.export_report_csv(report_data, output_path)
            elif options['output_format'] == 'pdf':
                service.export_report_pdf(report_data, output_path)
            
            self.stdout.write(
                self.style.SUCCESS(
                    f"Report generated successfully: {output_path}"
                )
            )
            
        except Exception as e:
            raise CommandError(f"Error generating report: {str(e)}")