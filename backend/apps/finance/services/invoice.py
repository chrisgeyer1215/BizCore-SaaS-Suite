# backend/apps/finance/services/invoice.py
"""
Invoice Service
Handles complete invoice lifecycle management including creation, approval, 
sending, payment tracking, and recurring invoices
"""

from typing import Dict, List, Optional, Any, Tuple
from decimal import Decimal
from datetime import date, datetime, timedelta
from django.db import transaction, models
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.template.loader import render_to_string
from django.core.mail import EmailMessage
from django.conf import settings
import logging

from .base import FinanceBaseService, ServiceResult
from .journal_entry import JournalEntryService
from ..models import (
    Invoice, InvoiceItem, Customer, Product, Account, 
    TaxCode, Currency, Payment, PaymentApplication
)

logger = logging.getLogger(__name__)


class InvoiceService(FinanceBaseService):
    """
    Comprehensive invoice management service
    """
    
    def get_service_name(self) -> str:
        return "InvoiceService"
    
    @transaction.atomic
    def create_invoice(self, invoice_data: Dict[str, Any]) -> ServiceResult:
        """
        Create a new invoice with line items and calculations
        
        Args:
            invoice_data: Dictionary containing invoice information
                Required fields:
                - customer_id: int
                - invoice_date: date
                - due_date: date
                - items: List[Dict] with line item details
                Optional fields:
                - reference_number: str
                - purchase_order_number: str
                - currency_code: str
                - invoice_type: str
                - discount_percentage: float
                - shipping_amount: float
                
        Returns:
            ServiceResult with created invoice information
        """
        def _create_invoice():
            # Validate required fields
            required_fields = ['customer_id', 'invoice_date', 'items']
            for field in required_fields:
                if field not in invoice_data:
                    raise ValidationError(f"Required field '{field}' is missing")
            
            # Validate customer
            try:
                customer = Customer.objects.get(
                    id=invoice_data['customer_id'], 
                    tenant=self.tenant
                )
            except Customer.DoesNotExist:
                raise ValidationError(f"Customer with ID {invoice_data['customer_id']} not found")
            
            # Set defaults
            invoice_date = invoice_data['invoice_date']
            if isinstance(invoice_date, str):
                invoice_date = datetime.strptime(invoice_date, '%Y-%m-%d').date()
            
            due_date = invoice_data.get('due_date')
            if not due_date:
                # Calculate due date from customer payment terms
                payment_terms_days = getattr(customer.financial_profile, 'payment_terms_days', 30) if hasattr(customer, 'financial_profile') else 30
                due_date = self.calculate_due_date(invoice_date, payment_terms_days)
            elif isinstance(due_date, str):
                due_date = datetime.strptime(due_date, '%Y-%m-%d').date()
            
            # Get currency
            currency_code = invoice_data.get('currency_code', self.base_currency.code)
            try:
                currency = Currency.objects.get(tenant=self.tenant, code=currency_code)
            except Currency.DoesNotExist:
                raise ValidationError(f"Currency '{currency_code}' not found")
            
            # Get exchange rate
            exchange_rate = self.get_exchange_rate(
                currency_code, 
                self.base_currency.code, 
                invoice_date
            )
            
            # Create invoice
            invoice = Invoice.objects.create(
                tenant=self.tenant,
                customer=customer,
                customer_email=customer.email,
                invoice_date=invoice_date,
                due_date=due_date,
                currency=currency,
                exchange_rate=exchange_rate,
                reference_number=invoice_data.get('reference_number', ''),
                purchase_order_number=invoice_data.get('purchase_order_number', ''),
                invoice_type=invoice_data.get('invoice_type', 'STANDARD'),
                discount_percentage=Decimal(str(invoice_data.get('discount_percentage', '0.00'))),
                shipping_amount=Decimal(str(invoice_data.get('shipping_amount', '0.00'))),
                description=invoice_data.get('description', ''),
                notes=invoice_data.get('notes', ''),
                customer_message=invoice_data.get('customer_message', ''),
                payment_terms=invoice_data.get('payment_terms', ''),
                status='DRAFT',
                created_by=self.user
            )
            
            # Set addresses
            if 'billing_address' in invoice_data:
                invoice.billing_address = invoice_data['billing_address']
            else:
                # Use customer's default billing address
                invoice.billing_address = getattr(customer, 'billing_address', {})
            
            if 'shipping_address' in invoice_data:
                invoice.shipping_address = invoice_data['shipping_address']
            else:
                # Use customer's default shipping address or billing address
                invoice.shipping_address = getattr(customer, 'shipping_address', invoice.billing_address)
            
            invoice.save()
            
            # Create invoice items
            item_errors = []
            for i, item_data in enumerate(invoice_data['items']):
                try:
                    self._create_invoice_item(invoice, item_data, i + 1)
                except ValidationError as e:
                    item_errors.append(f"Item {i + 1}: {str(e)}")
            
            if item_errors:
                raise ValidationError(item_errors)
            
            # Calculate totals
            invoice.calculate_totals()
            
            # Check credit limit if customer has one
            self._check_customer_credit_limit(customer, invoice.total_amount)
            
            return {
                'invoice_id': invoice.id,
                'invoice_number': invoice.invoice_number,
                'customer_name': customer.name,
                'subtotal': invoice.subtotal,
                'tax_amount': invoice.tax_amount,
                'total_amount': invoice.total_amount,
                'status': invoice.status,
                'due_date': invoice.due_date.isoformat(),
                'item_count': invoice.invoice_items.count()
            }
        
        return self.safe_execute("create_invoice", _create_invoice)
    
    def _create_invoice_item(self, invoice: Invoice, item_data: Dict[str, Any], 
                           line_number: int) -> InvoiceItem:
        """Create an invoice line item with validation and calculations"""
        
        # Validate required fields
        required_fields = ['description', 'quantity', 'unit_price']
        for field in required_fields:
            if field not in item_data:
                raise ValidationError(f"Required item field '{field}' is missing")
        
        # Get product if specified
        product = None
        if 'product_id' in item_data:
            try:
                product = Product.objects.get(
                    id=item_data['product_id'], 
                    tenant=self.tenant
                )
            except Product.DoesNotExist:
                raise ValidationError(f"Product with ID {item_data['product_id']} not found")
        
        # Get revenue account
        revenue_account = None
        if 'revenue_account_id' in item_data:
            try:
                revenue_account = Account.objects.get(
                    id=item_data['revenue_account_id'],
                    tenant=self.tenant,
                    account_type__in=['REVENUE', 'OTHER_INCOME']
                )
            except Account.DoesNotExist:
                raise ValidationError(f"Revenue account with ID {item_data['revenue_account_id']} not found")
        elif product and hasattr(product, 'default_revenue_account'):
            revenue_account = product.default_revenue_account
        else:
            # Get default revenue account
            revenue_account = self._get_default_revenue_account()
        
        # Get tax code
        tax_code = None
        if 'tax_code_id' in item_data:
            try:
                tax_code = TaxCode.objects.get(
                    id=item_data['tax_code_id'],
                    tenant=self.tenant
                )
            except TaxCode.DoesNotExist:
                raise ValidationError(f"Tax code with ID {item_data['tax_code_id']} not found")
        elif product and hasattr(product, 'default_tax_code'):
            tax_code = product.default_tax_code
        
        # Validate amounts
        quantity = Decimal(str(item_data['quantity']))
        unit_price = Decimal(str(item_data['unit_price']))
        discount_rate = Decimal(str(item_data.get('discount_rate', '0.00')))
        
        if quantity <= 0:
            raise ValidationError("Quantity must be greater than zero")
        
        if unit_price < 0:
            raise ValidationError("Unit price cannot be negative")
        
        if discount_rate < 0 or discount_rate > 100:
            raise ValidationError("Discount rate must be between 0 and 100")
        
        # Create the invoice item
        invoice_item = InvoiceItem.objects.create(
            tenant=self.tenant,
            invoice=invoice,
            line_number=line_number,
            product=product,
            description=item_data['description'],
            sku=item_data.get('sku', ''),
            quantity=quantity,
            unit_price=unit_price,
            discount_rate=discount_rate,
            revenue_account=revenue_account,
            tax_code=tax_code,
            item_type=item_data.get('item_type', 'PRODUCT'),
            project_id=item_data.get('project_id'),
            department_id=item_data.get('department_id'),
            location_id=item_data.get('location_id'),
            job_number=item_data.get('job_number', ''),
            warehouse_id=item_data.get('warehouse_id')
        )
        
        # Reserve inventory if product
        if product and invoice_item.item_type == 'PRODUCT':
            invoice_item.reserve_inventory()
        
        return invoice_item
    
    def _get_default_revenue_account(self) -> Account:
        """Get default revenue account"""
        revenue_account = Account.objects.filter(
            tenant=self.tenant,
            account_type='REVENUE',
            is_active=True
        ).first()
        
        if not revenue_account:
            # Create default revenue account
            revenue_account = Account.objects.create(
                tenant=self.tenant,
                code='4000',
                name='Sales Revenue',
                account_type='REVENUE',
                normal_balance='CREDIT',
                is_active=True,
                created_by=self.user
            )
        
        return revenue_account
    
    def _check_customer_credit_limit(self, customer: Customer, new_amount: Decimal) -> None:
        """Check if customer is within credit limit"""
        if hasattr(customer, 'financial_profile') and customer.financial_profile.credit_limit > 0:
            current_balance = customer.financial_profile.current_balance
            total_exposure = current_balance + new_amount
            
            if total_exposure > customer.financial_profile.credit_limit:
                raise ValidationError(
                    f"Customer credit limit exceeded. "
                    f"Current balance: {self.format_currency(current_balance)}, "
                    f"Credit limit: {self.format_currency(customer.financial_profile.credit_limit)}, "
                    f"New invoice: {self.format_currency(new_amount)}"
                )
    
    @transaction.atomic
    def approve_invoice(self, invoice_id: int) -> ServiceResult:
        """
        Approve an invoice and create journal entry
        
        Args:
            invoice_id: ID of invoice to approve
            
        Returns:
            ServiceResult with approval information
        """
        def _approve_invoice():
            try:
                invoice = Invoice.objects.get(id=invoice_id, tenant=self.tenant)
            except Invoice.DoesNotExist:
                raise ValidationError(f"Invoice with ID {invoice_id} not found")
            
            if invoice.status not in ['DRAFT', 'PENDING_APPROVAL']:
                raise ValidationError(f"Invoice cannot be approved from status '{invoice.status}'")
            
            # Validate invoice amounts
            if invoice.total_amount <= 0:
                raise ValidationError("Invoice total must be greater than zero")
            
            # Check if approval is required
            if (self.finance_settings.require_invoice_approval and 
                self.finance_settings.invoice_approval_limit and
                invoice.total_amount > self.finance_settings.invoice_approval_limit):
                
                # Check user permissions for approval
                if not self.check_user_permissions('approve_large_invoices'):
                    raise ValidationError("User does not have permission to approve large invoices")
            
            # Approve invoice
            invoice.approve_invoice(self.user)
            
            # Create journal entry
            journal_service = JournalEntryService(self.tenant, self.user)
            journal_result = journal_service.create_invoice_journal_entry(invoice)
            
            if not journal_result.success:
                raise ValidationError(f"Failed to create journal entry: {journal_result.message}")
            
            return {
                'invoice_id': invoice_id,
                'invoice_number': invoice.invoice_number,
                'status': invoice.status,
                'approved_by': invoice.approved_by.email if invoice.approved_by else None,
                'approved_date': invoice.approved_date.isoformat() if invoice.approved_date else None,
                'journal_entry_id': journal_result.data['result']['journal_entry_id']
            }
        
        return self.safe_execute("approve_invoice", _approve_invoice)
    
    @transaction.atomic
    def send_invoice(self, invoice_id: int, send_copy_to: Optional[List[str]] = None,
                    custom_message: Optional[str] = None) -> ServiceResult:
        """
        Send invoice via email to customer
        
        Args:
            invoice_id: ID of invoice to send
            send_copy_to: Additional email addresses to send copy to
            custom_message: Custom message to include in email
            
        Returns:
            ServiceResult with sending information
        """
        def _send_invoice():
            try:
                invoice = Invoice.objects.get(id=invoice_id, tenant=self.tenant)
            except Invoice.DoesNotExist:
                raise ValidationError(f"Invoice with ID {invoice_id} not found")
            
            if invoice.status not in ['APPROVED', 'OPEN']:
                raise ValidationError(f"Invoice must be approved before sending")
            
            if not invoice.customer_email:
                raise ValidationError("Customer email address is required to send invoice")
            
            # Generate PDF
            pdf_content = self._generate_invoice_pdf(invoice)
            
            # Prepare email
            subject = f"Invoice {invoice.invoice_number} from {self.finance_settings.company_name}"
            
            # Use custom message or default
            if custom_message:
                message = custom_message
            else:
                message = self._get_default_invoice_email_message(invoice)
            
            # Create email
            recipients = [invoice.customer_email]
            if send_copy_to:
                recipients.extend(send_copy_to)
            
            email = EmailMessage(
                subject=subject,
                body=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=recipients,
            )
            
            # Attach PDF
            email.attach(
                f"Invoice-{invoice.invoice_number}.pdf",
                pdf_content,
                'application/pdf'
            )
            
            # Send email
            try:
                email.send()
                email_sent = True
                error_message = None
            except Exception as e:
                email_sent = False
                error_message = str(e)
                logger.error(f"Failed to send invoice email: {e}")
            
            if email_sent:
                # Update invoice status
                invoice.status = 'SENT'
                invoice.sent_date = timezone.now()
                invoice.save(update_fields=['status', 'sent_date'])
                
                # Log the sending
                self.log_operation('invoice_sent', {
                    'invoice_id': invoice_id,
                    'invoice_number': invoice.invoice_number,
                    'recipients': recipients
                })
            
            return {
                'invoice_id': invoice_id,
                'invoice_number': invoice.invoice_number,
                'email_sent': email_sent,
                'recipients': recipients,
                'error_message': error_message,
                'sent_date': invoice.sent_date.isoformat() if invoice.sent_date else None
            }
        
        return self.safe_execute("send_invoice", _send_invoice)
    
    def _generate_invoice_pdf(self, invoice: Invoice) -> bytes:
        """Generate PDF content for invoice"""
        # This would integrate with your PDF generation system
        # For now, return placeholder content
        return b"PDF content placeholder"
    
    def _get_default_invoice_email_message(self, invoice: Invoice) -> str:
        """Get default email message for invoice"""
        return f"""
Dear {invoice.customer.name},

Please find attached invoice {invoice.invoice_number} for your recent purchase.

Invoice Details:
- Invoice Number: {invoice.invoice_number}
- Invoice Date: {invoice.invoice_date.strftime('%B %d, %Y')}
- Due Date: {invoice.due_date.strftime('%B %d, %Y')}
- Amount Due: {self.format_currency(invoice.amount_due, invoice.currency.code)}

If you have any questions about this invoice, please don't hesitate to contact us.

Thank you for your business!

{self.finance_settings.company_name}
        """.strip()
    
    @transaction.atomic
    def record_payment(self, invoice_id: int, payment_data: Dict[str, Any]) -> ServiceResult:
        """
        Record payment against invoice
        
        Args:
            invoice_id: ID of invoice to apply payment to
            payment_data: Payment information
                Required fields:
                - amount: Decimal
                - payment_date: date
                - payment_method: str
                - bank_account_id: int
                Optional fields:
                - reference_number: str
                - notes: str
                - discount_amount: Decimal
                
        Returns:
            ServiceResult with payment information
        """
        def _record_payment():
            try:
                invoice = Invoice.objects.get(id=invoice_id, tenant=self.tenant)
            except Invoice.DoesNotExist:
                raise ValidationError(f"Invoice with ID {invoice_id} not found")
            
            if invoice.status not in ['OPEN', 'SENT', 'VIEWED', 'PARTIAL']:
                raise ValidationError(f"Cannot apply payment to invoice with status '{invoice.status}'")
            
            # Validate payment amount
            payment_amount = Decimal(str(payment_data['amount']))
            discount_amount = Decimal(str(payment_data.get('discount_amount', '0.00')))
            total_application = payment_amount + discount_amount
            
            if payment_amount <= 0:
                raise ValidationError("Payment amount must be greater than zero")
            
            if total_application > invoice.amount_due:
                raise ValidationError(
                    f"Payment amount ({self.format_currency(total_application)}) "
                    f"cannot exceed amount due ({self.format_currency(invoice.amount_due)})"
                )
            
            # Create payment record
            payment = Payment.objects.create(
                tenant=self.tenant,
                payment_type='RECEIVED',
                customer=invoice.customer,
                amount=payment_amount,
                payment_date=payment_data['payment_date'],
                payment_method=payment_data['payment_method'],
                bank_account_id=payment_data['bank_account_id'],
                currency=invoice.currency,
                exchange_rate=invoice.exchange_rate,
                reference_number=payment_data.get('reference_number', ''),
                description=f"Payment for Invoice {invoice.invoice_number}",
                notes=payment_data.get('notes', ''),
                status='CLEARED'
            )
            
            # Apply payment to invoice
            payment.apply_to_invoices([{
                'invoice_id': invoice_id,
                'amount': payment_amount,
                'discount_amount': discount_amount
            }])
            
            # Create journal entry for payment
            journal_service = JournalEntryService(self.tenant, self.user)
            journal_result = journal_service.create_payment_journal_entry(payment)
            
            return {
                'payment_id': payment.id,
                'payment_number': payment.payment_number,
                'invoice_id': invoice_id,
                'invoice_number': invoice.invoice_number,
                'payment_amount': payment_amount,
                'discount_amount': discount_amount,
                'remaining_balance': invoice.amount_due - total_application,
                'invoice_status': invoice.status,
                'journal_entry_id': journal_result.data['result']['journal_entry_id'] if journal_result.success else None
            }
        
        return self.safe_execute("record_payment", _record_payment)
    
    def create_recurring_invoice(self, invoice_id: int, 
                               recurrence_data: Dict[str, Any]) -> ServiceResult:
        """
        Set up recurring invoice schedule
        
        Args:
            invoice_id: ID of template invoice
            recurrence_data: Recurrence settings
                Required fields:
                - interval_days: int
                - end_date: date (optional)
                - max_occurrences: int (optional)
                
        Returns:
            ServiceResult with recurring setup information
        """
        def _create_recurring():
            try:
                invoice = Invoice.objects.get(id=invoice_id, tenant=self.tenant)
            except Invoice.DoesNotExist:
                raise ValidationError(f"Invoice with ID {invoice_id} not found")
            
            if invoice.is_recurring:
                raise ValidationError("Invoice is already set up for recurring")
            
            # Validate recurrence settings
            interval_days = recurrence_data['interval_days']
            if interval_days <= 0:
                raise ValidationError("Interval days must be greater than zero")
            
            # Set up recurring schedule
            invoice.is_recurring = True
            invoice.recurring_interval_days = interval_days
            invoice.next_invoice_date = invoice.invoice_date + timedelta(days=interval_days)
            invoice.auto_send = recurrence_data.get('auto_send', False)
            
            # Set end conditions
            if 'end_date' in recurrence_data:
                invoice.recurring_end_date = recurrence_data['end_date']
            
            if 'max_occurrences' in recurrence_data:
                invoice.max_occurrences = recurrence_data['max_occurrences']
            
            invoice.save()
            
            return {
                'invoice_id': invoice_id,
                'invoice_number': invoice.invoice_number,
                'is_recurring': True,
                'interval_days': interval_days,
                'next_invoice_date': invoice.next_invoice_date.isoformat(),
                'auto_send': invoice.auto_send
            }
        
        return self.safe_execute("create_recurring_invoice", _create_recurring)
    
    def generate_next_recurring_invoice(self, parent_invoice_id: int) -> ServiceResult:
        """
        Generate next invoice in recurring series
        
        Args:
            parent_invoice_id: ID of parent recurring invoice
            
        Returns:
            ServiceResult with new invoice information
        """
        def _generate_next():
            try:
                parent_invoice = Invoice.objects.get(
                    id=parent_invoice_id, 
                    tenant=self.tenant,
                    is_recurring=True
                )
            except Invoice.DoesNotExist:
                raise ValidationError(f"Recurring invoice with ID {parent_invoice_id} not found")
            
            # Check if we should generate next invoice
            if not parent_invoice.next_invoice_date:
                raise ValidationError("No next invoice date set")
            
            if parent_invoice.next_invoice_date > timezone.now().date():
                raise ValidationError("Next invoice date has not arrived yet")
            
            # Create new invoice based on parent
            new_invoice_date = parent_invoice.next_invoice_date
            new_due_date = self.calculate_due_date(
                new_invoice_date, 
                (parent_invoice.due_date - parent_invoice.invoice_date).days
            )
            
            new_invoice = Invoice.objects.create(
                tenant=self.tenant,
                customer=parent_invoice.customer,
                customer_email=parent_invoice.customer_email,
                invoice_date=new_invoice_date,
                due_date=new_due_date,
                currency=parent_invoice.currency,
                exchange_rate=self.get_exchange_rate(
                    parent_invoice.currency.code,
                    self.base_currency.code,
                    new_invoice_date
                ),
                invoice_type=parent_invoice.invoice_type,
                billing_address=parent_invoice.billing_address,
                shipping_address=parent_invoice.shipping_address,
                description=parent_invoice.description,
                notes=parent_invoice.notes,
                customer_message=parent_invoice.customer_message,
                payment_terms=parent_invoice.payment_terms,
                discount_percentage=parent_invoice.discount_percentage,
                shipping_amount=parent_invoice.shipping_amount,
                parent_invoice=parent_invoice,
                status='DRAFT'
            )
            
            # Copy invoice items
            for parent_item in parent_invoice.invoice_items.all():
                InvoiceItem.objects.create(
                    tenant=self.tenant,
                    invoice=new_invoice,
                    line_number=parent_item.line_number,
                    product=parent_item.product,
                    description=parent_item.description,
                    sku=parent_item.sku,
                    quantity=parent_item.quantity,
                    unit_price=parent_item.unit_price,
                    discount_rate=parent_item.discount_rate,
                    revenue_account=parent_item.revenue_account,
                    tax_code=parent_item.tax_code,
                    item_type=parent_item.item_type,
                    project=parent_item.project,
                    department=parent_item.department,
                    location=parent_item.location,
                    job_number=parent_item.job_number,
                    warehouse=parent_item.warehouse
                )
            
            # Calculate totals
            new_invoice.calculate_totals()
            
            # Update parent invoice next date
            parent_invoice.next_invoice_date = new_invoice_date + timedelta(
                days=parent_invoice.recurring_interval_days
            )
            parent_invoice.save(update_fields=['next_invoice_date'])
            
            # Auto-approve and send if configured
            if parent_invoice.auto_send:
                approve_result = self.approve_invoice(new_invoice.id)
                if approve_result.success:
                    send_result = self.send_invoice(new_invoice.id)
                    return {
                        'invoice_id': new_invoice.id,
                        'invoice_number': new_invoice.invoice_number,
                        'parent_invoice_id': parent_invoice_id,
                        'auto_approved': True,
                        'auto_sent': send_result.success,
                        'total_amount': new_invoice.total_amount
                    }
            
            return {
                'invoice_id': new_invoice.id,
                'invoice_number': new_invoice.invoice_number,
                'parent_invoice_id': parent_invoice_id,
                'auto_approved': False,
                'auto_sent': False,
                'total_amount': new_invoice.total_amount
            }
        
        return self.safe_execute("generate_next_recurring_invoice", _generate_next)
    
    def get_invoice_aging_analysis(self, as_of_date: Optional[date] = None) -> ServiceResult:
        """
        Get aging analysis for all outstanding invoices
        
        Args:
            as_of_date: Date to calculate aging as of
            
        Returns:
            ServiceResult with aging analysis data
        """
        def _get_aging_analysis():
            if as_of_date is None:
                as_of_date = timezone.now().date()
            
            # Get outstanding invoices
            outstanding_invoices = Invoice.objects.filter(
                tenant=self.tenant,
                status__in=['OPEN', 'SENT', 'VIEWED', 'PARTIAL'],
                invoice_date__lte=as_of_date
            ).select_related('customer')
            
            aging_buckets = {
                'current': Decimal('0.00'),          # 0-30 days
                'days_31_60': Decimal('0.00'),       # 31-60 days
                'days_61_90': Decimal('0.00'),       # 61-90 days
                'days_91_120': Decimal('0.00'),      # 91-120 days
                'over_120': Decimal('0.00')          # Over 120 days
            }
            
            customer_aging = {}
            total_outstanding = Decimal('0.00')
            
            for invoice in outstanding_invoices:
                days_overdue = (as_of_date - invoice.due_date).days
                amount_due = invoice.amount_due
                total_outstanding += amount_due
                
                # Determine aging bucket
                if days_overdue <= 0:
                    bucket = 'current'
                elif days_overdue <= 30:
                    bucket = 'current'
                elif days_overdue <= 60:
                    bucket = 'days_31_60'
                elif days_overdue <= 90:
                    bucket = 'days_61_90'
                elif days_overdue <= 120:
                    bucket = 'days_91_120'
                else:
                    bucket = 'over_120'
                
                aging_buckets[bucket] += amount_due
                
                # Customer aging detail
                customer_name = invoice.customer.name
                if customer_name not in customer_aging:
                    customer_aging[customer_name] = {
                        'customer_id': invoice.customer.id,
                        'total_outstanding': Decimal('0.00'),
                        'current': Decimal('0.00'),
                        'days_31_60': Decimal('0.00'),
                        'days_61_90': Decimal('0.00'),
                        'days_91_120': Decimal('0.00'),
                        'over_120': Decimal('0.00'),
                        'invoices': []
                    }
                
                customer_aging[customer_name]['total_outstanding'] += amount_due
                customer_aging[customer_name][bucket] += amount_due
                customer_aging[customer_name]['invoices'].append({
                    'invoice_id': invoice.id,
                    'invoice_number': invoice.invoice_number,
                    'invoice_date': invoice.invoice_date.isoformat(),
                    'due_date': invoice.due_date.isoformat(),
                    'amount_due': amount_due,
                    'days_overdue': max(0, days_overdue),
                    'aging_bucket': bucket
                })
            
            return {
                'as_of_date': as_of_date.isoformat(),
                'total_outstanding': total_outstanding,
                'aging_summary': aging_buckets,
                'customer_detail': customer_aging,
                'invoice_count': outstanding_invoices.count(),
                'currency': self.base_currency.code
            }
        
        return self.safe_execute("get_invoice_aging_analysis", _get_aging_analysis)