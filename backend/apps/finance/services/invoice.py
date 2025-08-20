"""
Invoice Service - Management and Processing
"""

from django.core.mail import EmailMessage
from django.template.loader import render_to_string
from django.conf import settings
from django.utils import timezone
from decimal import Decimal
from datetime import date, timedelta
from typing import Dict, List, Optional
import io
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors

from ..models import Invoice, InvoiceItem, Payment, PaymentApplication
from .accounting import AccountingService


class InvoiceService(AccountingService):
    """Invoice management and processing service"""

    def send_invoice(self, invoice: Invoice, send_copy_to: List[str] = None) -> Dict:
        """Send invoice via email"""
        try:
            # Generate PDF
            pdf_content = self.generate_pdf(invoice)
            
            # Prepare email
            subject = f'Invoice {invoice.invoice_number} from {self.settings.company_name}'
            
            context = {
                'invoice': invoice,
                'company': self.settings,
                'customer': invoice.customer
            }
            
            # Render email template
            html_content = render_to_string('finance/emails/invoice.html', context)
            text_content = render_to_string('finance/emails/invoice.txt', context)
            
            # Create email
            email = EmailMessage(
                subject=subject,
                body=text_content,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[invoice.customer_email],
                cc=send_copy_to or []
            )
            
            # Attach PDF
            email.attach(
                f'invoice_{invoice.invoice_number}.pdf',
                pdf_content,
                'application/pdf'
            )
            
            # Send email
            email.send()
            
            # Update invoice status
            invoice.status = 'SENT'
            invoice.sent_date = timezone.now()
            invoice.save(update_fields=['status', 'sent_date'])
            
            return {
                'success': True,
                'message': 'Invoice sent successfully',
                'sent_to': invoice.customer_email,
                'sent_date': invoice.sent_date
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }

    def generate_pdf(self, invoice: Invoice) -> bytes:
        """Generate PDF invoice"""
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter)
        styles = getSampleStyleSheet()
        story = []
        
        # Company header
        company_style = ParagraphStyle(
            'CompanyHeader',
            parent=styles['Heading1'],
            fontSize=18,
            spaceAfter=20
        )
        story.append(Paragraph(self.settings.company_name, company_style))
        
        # Company address
        if self.settings.company_address:
            address_lines = []
            address = self.settings.company_address
            if address.get('street'):
                address_lines.append(address['street'])
            if address.get('city') and address.get('state'):
                address_lines.append(f"{address['city']}, {address['state']} {address.get('postal_code', '')}")
            if address.get('country'):
                address_lines.append(address['country'])
            
            for line in address_lines:
                story.append(Paragraph(line, styles['Normal']))
        
        story.append(Spacer(1, 20))
        
        # Invoice header
        invoice_data = [
            ['Invoice Number:', invoice.invoice_number],
            ['Invoice Date:', invoice.invoice_date.strftime('%B %d, %Y')],
            ['Due Date:', invoice.due_date.strftime('%B %d, %Y')],
            ['Amount Due:', f'{invoice.currency.symbol}{invoice.amount_due:,.2f}']
        ]
        
        if invoice.reference_number:
            invoice_data.append(['Reference:', invoice.reference_number])
        
        invoice_table = Table(invoice_data, colWidths=[1.5*inch, 2*inch])
        invoice_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ]))
        story.append(invoice_table)
        story.append(Spacer(1, 20))
        
        # Bill to section
        story.append(Paragraph('Bill To:', styles['Heading3']))
        story.append(Paragraph(invoice.customer.name, styles['Normal']))
        
        if invoice.billing_address:
            address = invoice.billing_address
            if address.get('street'):
                story.append(Paragraph(address['street'], styles['Normal']))
            if address.get('city') and address.get('state'):
                story.append(Paragraph(f"{address['city']}, {address['state']} {address.get('postal_code', '')}", styles['Normal']))
        
        story.append(Spacer(1, 20))
        
        # Line items
        items_data = [['Description', 'Qty', 'Unit Price', 'Amount']]
        
        for item in invoice.invoice_items.all():
            items_data.append([
                item.description,
                f'{item.quantity:,.2f}',
                f'{invoice.currency.symbol}{item.unit_price:,.2f}',
                f'{invoice.currency.symbol}{item.line_total:,.2f}'
            ])
        
        # Totals
        items_data.extend([
            ['', '', 'Subtotal:', f'{invoice.currency.symbol}{invoice.subtotal:,.2f}'],
            ['', '', 'Tax:', f'{invoice.currency.symbol}{invoice.tax_amount:,.2f}'],
            ['', '', 'Total:', f'{invoice.currency.symbol}{invoice.total_amount:,.2f}']
        ])
        
        items_table = Table(items_data, colWidths=[3*inch, 0.75*inch, 1*inch, 1*inch])
        items_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (1, 1), (-1, -1), 'RIGHT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('GRID', (0, 0), (-1, -4), 1, colors.black),
            ('LINEBELOW', (0, -3), (-1, -1), 1, colors.black),
            ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ]))
        
        story.append(items_table)
        story.append(Spacer(1, 20))
        
        # Payment terms
        if invoice.payment_terms:
            story.append(Paragraph('Payment Terms:', styles['Heading4']))
            story.append(Paragraph(invoice.payment_terms, styles['Normal']))
            story.append(Spacer(1, 10))
        
        # Notes
        if invoice.notes:
            story.append(Paragraph('Notes:', styles['Heading4']))
            story.append(Paragraph(invoice.notes, styles['Normal']))
        
        # Build PDF
        doc.build(story)
        buffer.seek(0)
        return buffer.getvalue()

    def record_payment(self, invoice: Invoice, payment_data: Dict) -> Payment:
        """Record payment against invoice"""
        from .payment import PaymentService
        
        payment_service = PaymentService(self.tenant)
        
        # Create payment
        payment = payment_service.create_received_payment(
            customer=invoice.customer,
            amount=payment_data['amount'],
            payment_method=payment_data['payment_method'],
            payment_date=payment_data.get('payment_date', date.today()),
            bank_account_id=payment_data['bank_account_id'],
            reference_number=payment_data.get('reference_number'),
            description=f'Payment for Invoice {invoice.invoice_number}'
        )
        
        # Apply to invoice
        PaymentApplication.objects.create(
            tenant=self.tenant,
            payment=payment,
            invoice=invoice,
            amount_applied=payment_data['amount'],
            discount_amount=payment_data.get('discount_amount', Decimal('0.00'))
        )
        
        return payment

    def create_credit_note(self, invoice: Invoice, credit_data: Dict) -> Invoice:
        """Create credit note for invoice"""
        from django.db import transaction
        
        with transaction.atomic():
            credit_note = Invoice.objects.create(
                tenant=self.tenant,
                customer=invoice.customer,
                invoice_type='CREDIT_NOTE',
                invoice_date=credit_data.get('credit_date', date.today()),
                due_date=credit_data.get('credit_date', date.today()),
                currency=invoice.currency,
                exchange_rate=invoice.exchange_rate,
                description=f'Credit Note for Invoice {invoice.invoice_number}',
                notes=credit_data.get('notes', ''),
                source_quote=invoice  # Link to original invoice
            )
            
            # Copy items with negative amounts
            for item in invoice.invoice_items.all():
                credit_amount = credit_data.get('items', {}).get(str(item.id), item.line_total)
                
                if credit_amount > 0:
                    InvoiceItem.objects.create(
                        tenant=self.tenant,
                        invoice=credit_note,
                        line_number=item.line_number,
                        item_type=item.item_type,
                        product=item.product,
                        description=f'Credit: {item.description}',
                        quantity=-abs(item.quantity),  # Negative quantity
                        unit_price=item.unit_price,
                        revenue_account=item.revenue_account,
                        tax_code=item.tax_code
                    )
            
            # Calculate totals
            credit_note.calculate_totals()
            credit_note.status = 'APPROVED'
            credit_note.save()
            
            # Create journal entry
            from .journal_entry import JournalEntryService
            journal_service = JournalEntryService(self.tenant)
            journal_service.create_invoice_journal_entry(credit_note)
            
            return credit_note

    def get_invoice_aging(self, as_of_date: date = None) -> Dict:
        """Get invoice aging report"""
        if not as_of_date:
            as_of_date = date.today()
        
        invoices = Invoice.objects.filter(
            tenant=self.tenant,
            status__in=['OPEN', 'SENT', 'VIEWED', 'PARTIAL'],
            amount_due__gt=0
        )
        
        aging_buckets = {
            'current': Decimal('0.00'),
            'days_1_30': Decimal('0.00'),
            'days_31_60': Decimal('0.00'),
            'days_61_90': Decimal('0.00'),
            'over_90': Decimal('0.00')
        }
        
        for invoice in invoices:
            days_overdue = (as_of_date - invoice.due_date).days
            
            if days_overdue <= 0:
                aging_buckets['current'] += invoice.base_currency_amount_due
            elif days_overdue <= 30:
                aging_buckets['days_1_30'] += invoice.base_currency_amount_due
            elif days_overdue <= 60:
                aging_buckets['days_31_60'] += invoice.base_currency_amount_due
            elif days_overdue <= 90:
                aging_buckets['days_61_90'] += invoice.base_currency_amount_due
            else:
                aging_buckets['over_90'] += invoice.base_currency_amount_due
        
        total = sum(aging_buckets.values())
        
        return {
            'as_of_date': as_of_date,
            'aging_buckets': aging_buckets,
            'total_outstanding': total,
            'percentages': {
                bucket: (amount / total * 100) if total > 0 else 0
                for bucket, amount in aging_buckets.items()
            }
        }