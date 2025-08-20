# backend/apps/finance/services/vendor.py

"""
Vendor Service - Vendor Management and Analytics
"""

from django.db.models import Sum, Avg, Count, Q
from decimal import Decimal
from datetime import date, timedelta
from typing import Dict, List

from ..models import Vendor, Bill, Payment, PaymentApplication
from .accounting import AccountingService


class VendorService(AccountingService):
    """Vendor management and analytics service"""

    def get_vendor_balance(self, vendor_id: int) -> Decimal:
        """Get current outstanding balance for vendor"""
        
        vendor = Vendor.objects.get(id=vendor_id, tenant=self.tenant)
        
        # Calculate from unpaid bills
        outstanding_bills = Bill.objects.filter(
            tenant=self.tenant,
            vendor=vendor,
            status__in=['OPEN', 'APPROVED', 'PARTIAL'],
            amount_due__gt=0
        ).aggregate(
            total=Sum('base_currency_amount_due')
        )['total'] or Decimal('0.00')
        
        return outstanding_bills

    def get_vendor_payment_history(self, vendor_id: int, days: int = 365) -> Dict:
        """Get vendor payment history and metrics"""
        
        vendor = Vendor.objects.get(id=vendor_id, tenant=self.tenant)
        cutoff_date = date.today() - timedelta(days=days)
        
        # Get payments made to this vendor
        payments = Payment.objects.filter(
            tenant=self.tenant,
            vendor=vendor,
            payment_type='MADE',
            payment_date__gte=cutoff_date
        )
        
        # Get bills for this vendor
        bills = Bill.objects.filter(
            tenant=self.tenant,
            vendor=vendor,
            bill_date__gte=cutoff_date
        )
        
        # Calculate payment metrics
        total_payments = payments.aggregate(
            total=Sum('base_currency_amount')
        )['total'] or Decimal('0.00')
        
        total_bills = bills.aggregate(
            total=Sum('base_currency_total')
        )['total'] or Decimal('0.00')
        
        # Calculate average payment time
        paid_bills = bills.filter(status='PAID')
        payment_times = []
        
        for bill in paid_bills:
            # Find payments for this bill
            bill_payments = PaymentApplication.objects.filter(
                tenant=self.tenant,
                bill=bill,
                payment__payment_type='MADE'
            ).order_by('payment__payment_date')
            
            if bill_payments.exists():
                first_payment = bill_payments.first()
                days_to_pay = (first_payment.payment.payment_date - bill.bill_date).days
                payment_times.append(days_to_pay)
        
        avg_payment_days = sum(payment_times) / len(payment_times) if payment_times else 0
        
        return {
            'vendor_id': vendor_id,
            'vendor_name': vendor.company_name,
            'period_days': days,
            'total_payments': float(total_payments),
            'total_bills': float(total_bills),
            'payment_count': payments.count(),
            'bill_count': bills.count(),
            'average_payment_days': round(avg_payment_days, 1),
            'on_time_payments': len([days for days in payment_times if days <= vendor.payment_terms_days]),
            'late_payments': len([days for days in payment_times if days > vendor.payment_terms_days]),
            'current_balance': float(self.get_vendor_balance(vendor_id))
        }

    def get_vendor_performance_metrics(self, vendor_id: int) -> Dict:
        """Get comprehensive vendor performance metrics"""
        
        vendor = Vendor.objects.get(id=vendor_id, tenant=self.tenant)
        
        # Last 12 months of data
        one_year_ago = date.today() - timedelta(days=365)
        
        bills = Bill.objects.filter(
            tenant=self.tenant,
            vendor=vendor,
            bill_date__gte=one_year_ago
        )
        
        # Purchase volume
        total_purchases = bills.aggregate(
            total=Sum('base_currency_total')
        )['total'] or Decimal('0.00')
        
        # Payment performance
        payment_history = self.get_vendor_payment_history(vendor_id, 365)
        
        # Calculate vendor ranking among all vendors
        all_vendors_spending = Bill.objects.filter(
            tenant=self.tenant,
            bill_date__gte=one_year_ago
        ).values('vendor').annotate(
            total_spending=Sum('base_currency_total')
        ).order_by('-total_spending')
        
        vendor_rank = next(
            (index + 1 for index, v in enumerate(all_vendors_spending) 
             if v['vendor'] == vendor_id), 
            None
        )
        
        return {
            'vendor_id': vendor_id,
            'vendor_name': vendor.company_name,
            'vendor_type': vendor.vendor_type,
            'total_purchases_12m': float(total_purchases),
            'average_bill_amount': float(total_purchases / bills.count()) if bills.count() > 0 else 0,
            'bill_count_12m': bills.count(),
            'payment_performance': payment_history,
            'vendor_rank': vendor_rank,
            'total_vendors': all_vendors_spending.count(),
            'quality_rating': float(vendor.quality_rating),
            'on_time_delivery_rate': float(vendor.on_time_delivery_rate),
            'credit_rating': vendor.status,
            'is_preferred_vendor': total_purchases > 10000,  # Custom business logic
        }

    def get_spending_analysis(self, start_date: date = None, end_date: date = None) -> Dict:
        """Get vendor spending analysis"""
        
        if not start_date:
            start_date = date.today() - timedelta(days=365)
        if not end_date:
            end_date = date.today()
        
        bills = Bill.objects.filter(
            tenant=self.tenant,
            bill_date__range=[start_date, end_date],
            status__in=['APPROVED', 'PAID', 'PARTIAL']
        )
        
        # Top vendors by spending
        top_vendors = bills.values(
            'vendor__id', 'vendor__company_name', 'vendor__vendor_type'
        ).annotate(
            total_spending=Sum('base_currency_total'),
            bill_count=Count('id'),
            avg_bill_amount=Avg('base_currency_total')
        ).order_by('-total_spending')[:10]
        
        # Spending by vendor type
        spending_by_type = bills.values('vendor__vendor_type').annotate(
            total_spending=Sum('base_currency_total'),
            vendor_count=Count('vendor', distinct=True)
        ).order_by('-total_spending')
        
        # Monthly spending trend
        monthly_spending = []
        current_date = start_date
        while current_date <= end_date:
            month_start = current_date.replace(day=1)
            if current_date.month == 12:
                month_end = month_start.replace(year=month_start.year + 1, month=1) - timedelta(days=1)
            else:
                month_end = month_start.replace(month=month_start.month + 1) - timedelta(days=1)
            
            month_bills = bills.filter(bill_date__range=[month_start, min(month_end, end_date)])
            monthly_total = month_bills.aggregate(
                total=Sum('base_currency_total')
            )['total'] or Decimal('0.00')
            
            monthly_spending.append({
                'month': month_start.strftime('%Y-%m'),
                'total_spending': float(monthly_total),
                'bill_count': month_bills.count()
            })
            
            if current_date.month == 12:
                current_date = current_date.replace(year=current_date.year + 1, month=1)
            else:
                current_date = current_date.replace(month=current_date.month + 1)
        
        total_spending = bills.aggregate(
            total=Sum('base_currency_total')
        )['total'] or Decimal('0.00')
        
        return {
            'period': {
                'start_date': start_date,
                'end_date': end_date
            },
            'total_spending': float(total_spending),
            'total_bills': bills.count(),
            'unique_vendors': bills.values('vendor').distinct().count(),
            'average_bill_amount': float(total_spending / bills.count()) if bills.count() > 0 else 0,
            'top_vendors': [
                {
                    'vendor_id': vendor['vendor__id'],
                    'vendor_name': vendor['vendor__company_name'],
                    'vendor_type': vendor['vendor__vendor_type'],
                    'total_spending': float(vendor['total_spending']),
                    'bill_count': vendor['bill_count'],
                    'avg_bill_amount': float(vendor['avg_bill_amount']),
                    'percentage_of_total': float(vendor['total_spending'] / total_spending * 100) if total_spending > 0 else 0
                }
                for vendor in top_vendors
            ],
            'spending_by_type': [
                {
                    'vendor_type': item['vendor__vendor_type'],
                    'total_spending': float(item['total_spending']),
                    'vendor_count': item['vendor_count'],
                    'percentage_of_total': float(item['total_spending'] / total_spending * 100) if total_spending > 0 else 0
                }
                for item in spending_by_type
            ],
            'monthly_trend': monthly_spending
        }