import csv
import json
from io import StringIO
from django.core.management.base import BaseCommand
from django.core.mail import EmailMessage
from django.utils import timezone
from django.conf import settings
from apps.ecommerce.models import Order, OrderItem
from datetime import datetime, timedelta


class Command(BaseCommand):
    help = 'Process and export order data for reporting'

    def add_arguments(self, parser):
        parser.add_argument(
            '--date-from',
            type=str,
            help='Export orders from date (YYYY-MM-DD)'
        )
        parser.add_argument(
            '--date-to',
            type=str,
            help='Export orders to date (YYYY-MM-DD)'
        )
        parser.add_argument(
            '--format',
            type=str,
            choices=['csv', 'json'],
            default='csv',
            help='Export format'
        )
        parser.add_argument(
            '--email',
            type=str,
            help='Email address to send export to'
        )
        parser.add_argument(
            '--tenant-id',
            type=str,
            help='Specific tenant ID'
        )

    def handle(self, *args, **options):
        date_from = options.get('date_from')
        date_to = options.get('date_to')
        export_format = options.get('format')
        email = options.get('email')
        tenant_id = options.get('tenant_id')

        # Parse dates
        if date_from:
            date_from = datetime.strptime(date_from, '%Y-%m-%d').date()
        else:
            date_from = (timezone.now() - timedelta(days=30)).date()

        if date_to:
            date_to = datetime.strptime(date_to, '%Y-%m-%d').date()
        else:
            date_to = timezone.now().date()

        # Build queryset
        orders = Order.objects.filter(
            order_date__date__range=[date_from, date_to]
        ).select_related('customer').prefetch_related('items')
        
        if tenant_id:
            orders = orders.filter(tenant_id=tenant_id)

        self.stdout.write(f'Exporting {orders.count()} orders...')

        # Generate export
        if export_format == 'csv':
            export_data = self.generate_csv_export(orders)
            filename = f'orders_export_{date_from}_{date_to}.csv'
            content_type = 'text/csv'
        else:
            export_data = self.generate_json_export(orders)
            filename = f'orders_export_{date_from}_{date_to}.json'
            content_type = 'application/json'

        # Email export if requested
        if email:
            self.email_export(export_data, filename, content_type, email)
        else:
            # Write to stdout
            self.stdout.write(export_data)

        self.stdout.write(
            self.style.SUCCESS(f'Export completed: {orders.count()} orders')
        )

    def generate_csv_export(self, orders):
        """Generate CSV export of orders"""
        output = StringIO()
        writer = csv.writer(output)
        
        # Headers
        writer.writerow([
            'Order Number', 'Customer Email', 'Order Date', 'Status',
            'Payment Status', 'Total Amount', 'Currency', 'Items Count',
            'Customer Name', 'Billing Country', 'Shipping Country'
        ])
        
        # Data rows
        for order in orders:
            writer.writerow([
                order.order_number,
                order.customer_email,
                order.order_date.strftime('%Y-%m-%d %H:%M:%S'),
                order.status,
                order.payment_status,
                str(order.total_amount),
                order.currency,
                order.items.count(),
                order.customer_name if hasattr(order, 'customer_name') else '',
                order.billing_address.get('country', '') if order.billing_address else '',
                order.shipping_address.get('country', '') if order.shipping_address else '',
            ])
        
        return output.getvalue()

    def generate_json_export(self, orders):
        """Generate JSON export of orders"""
        export_data = []
        
        for order in orders:
            order_data = {
                'order_number': order.order_number,
                'customer_email': order.customer_email,
                'order_date': order.order_date.isoformat(),
                'status': order.status,
                'payment_status': order.payment_status,
                'total_amount': str(order.total_amount),
                'currency': order.currency,
                'billing_address': order.billing_address,
                'shipping_address': order.shipping_address,
                'items': []
            }
            
            # Add order items
            for item in order.items.all():
                item_data = {
                    'title': item.title,
                    'sku': item.sku,
                    'quantity': item.quantity,
                    'price': str(item.price),
                    'line_total': str(item.line_total)
                }
                order_data['items'].append(item_data)
            
            export_data.append(order_data)
        
        return json.dumps(export_data, indent=2)

    def email_export(self, export_data, filename, content_type, email):
        """Email export to specified address"""
        subject = f'Order Export - {filename}'
        message = 'Please find the order export attached.'
        
        email_message = EmailMessage(
            subject=subject,
            body=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[email]
        )
        
        email_message.attach(filename, export_data, content_type)
        email_message.send()
        
        self.stdout.write(f'Export emailed to {email}')
