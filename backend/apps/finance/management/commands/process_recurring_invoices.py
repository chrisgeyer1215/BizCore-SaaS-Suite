# backend/apps/finance/management/commands/process_recurring_invoices.py

"""
Process Recurring Invoices
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from apps.finance.models import Invoice
from apps.finance.services.recurring_invoice import RecurringInvoiceService
from datetime import date


class Command(BaseCommand):
    """Process recurring invoices"""
    
    help = 'Process recurring invoices that are due'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--tenant',
            type=str,
            help='Process for specific tenant only'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be processed without creating invoices'
        )

    def handle(self, *args, **options):
        tenant_filter = {}
        if options['tenant']:
            tenant_filter['tenant__schema_name'] = options['tenant']
        
        # Find recurring invoices due for processing
        due_invoices = Invoice.objects.filter(
            is_recurring=True,
            next_invoice_date__lte=date.today(),
            **tenant_filter
        )
        
        total_processed = 0
        
        for invoice in due_invoices:
            service = RecurringInvoiceService(invoice.tenant)
            
            if options['dry_run']:
                self.stdout.write(
                    f"Would create recurring invoice for: {invoice.invoice_number} "
                    f"(Customer: {invoice.customer.name})"
                )
            else:
                try:
                    new_invoice = service.create_next_invoice(invoice)
                    total_processed += 1
                    
                    self.stdout.write(
                        f"Created invoice {new_invoice.invoice_number} "
                        f"from recurring invoice {invoice.invoice_number}"
                    )
                except Exception as e:
                    self.stderr.write(
                        f"Error processing {invoice.invoice_number}: {str(e)}"
                    )
        
        if options['dry_run']:
            self.stdout.write(
                self.style.WARNING(f"DRY RUN: Would process {due_invoices.count()} invoices")
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(f"Successfully processed {total_processed} recurring invoices")
            )