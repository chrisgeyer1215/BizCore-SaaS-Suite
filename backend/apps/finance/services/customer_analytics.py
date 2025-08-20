# backend/apps/finance/services/customer_analytics.py

"""
Customer Analytics Service - Customer Financial Analysis
"""

from django.db.models import Sum, Avg, Count, Q, F
from decimal import Decimal
from datetime import date, timedelta
from typing import Dict, List

from ..models import Customer, Invoice, Payment, PaymentApplication, CustomerFinancialProfile
from .accounting import AccountingService


class CustomerAnalyticsService(AccountingService):
    """Customer financial analytics and insights service"""

    def update_customer_payment_history(self, customer: Customer):
        """Update customer payment history metrics"""
        
        # Get customer's financial profile
        profile, created = CustomerFinancialProfile.objects.get_or_create(
            tenant=self.tenant,
            customer=customer,
            defaults={
                'credit_limit': Decimal('5000.00'),
                'payment_terms_days': 30,
                'credit_rating': 'UNRATED'
            }
        )
        
        # Calculate payment metrics
        paid_invoices = Invoice.objects.filter(
            tenant=self.tenant,
            customer=customer,
            status='PAID'
        )
        
        if paid_invoices.exists():
            # Calculate average days to pay
            payment_times = []
            for invoice in paid_invoices:
                payments = PaymentApplication.objects.filter(
                    tenant=self.tenant,
                    invoice=invoice
                ).order_by('payment__payment_date')
                
                if payments.exists():
                    first_payment = payments.first()
                    days_to_pay = (first_payment.payment.payment_date - invoice.invoice_date).days
                    payment_times.append(days_to_pay)
            
            if payment_times:
                profile.average_days_to_pay = Decimal(str(sum(payment_times) / len(payment_times)))
                
                # Calculate payment history score (0-100)
                on_time_payments = len([days for days in payment_times if days <= profile.payment_terms_days])
                profile.payment_history_score = int((on_time_payments / len(payment_times)) * 100)
        
        # Update total sales and payments
        total_sales = Invoice.objects.filter(
            tenant=self.tenant,
            customer=customer,
            status__in=['PAID', 'PARTIAL', 'OPEN']
        ).aggregate(total=Sum('base_currency_total'))['total'] or Decimal('0.00')
        
        total_payments = Payment.objects.filter(
            tenant=self.tenant,
            customer=customer,
            payment_type='RECEIVED'
        ).aggregate(total=Sum('base_currency_amount'))['total'] or Decimal('0.00')
        
        current_balance = Invoice.objects.filter(
            tenant=self.tenant,
            customer=customer,
            status__in=['OPEN', 'SENT', 'VIEWED', 'PARTIAL'],
            amount_due__gt=0
        ).aggregate(total=Sum('base_currency_amount_due'))['total'] or Decimal('0.00')
        
        profile.total_sales = total_sales
        profile.total_payments = total_payments
        profile.current_balance = current_balance
        
        # Update highest balance
        if current_balance > profile.highest_balance:
            profile.highest_balance = current_balance
        
        # Update risk assessment
        if profile.current_balance > profile.credit_limit:
            profile.risk_level = 'HIGH'
        elif profile.payment_history_score < 70:
            profile.risk_level = 'MEDIUM'
        else:
            profile.risk_level = 'LOW'
        
        # Update collection priority
        if profile.current_balance > profile.credit_limit * Decimal('1.2'):
            profile.collection_priority = 'URGENT'
        elif any(
            invoice.days_overdue > 60 
            for invoice in Invoice.objects.filter(
                tenant=self.tenant,
                customer=customer,
                status__in=['OPEN', 'SENT', 'VIEWED', 'PARTIAL']
            )
        ):
            profile.collection_priority = 'HIGH'
        else:
            profile.collection_priority = 'NORMAL'
        
        profile.save()

    def get_customer_financial_summary(self, customer_id: int, days: int = 365) -> Dict:
        """Get comprehensive customer financial summary"""
        
        customer = Customer.objects.get(id=customer_id, tenant=self.tenant)
        cutoff_date = date.today() - timedelta(days=days)
        
        # Update payment history first
        self.update_customer_payment_history(customer)
        
        profile = customer.financial_profile
        
        # Get invoices for the period
        invoices = Invoice.objects.filter(
            tenant=self.tenant,
            customer=customer,
            invoice_date__gte=cutoff_date
        )
        
        # Get payments for the period  
        payments = Payment.objects.filter(
            tenant=self.tenant,
            customer=customer,
            payment_type='RECEIVED',
            payment_date__gte=cutoff_date
        )
        
        # Calculate period totals
        period_sales = invoices.aggregate(
            total=Sum('base_currency_total')
        )['total'] or Decimal('0.00')
        
        period_payments = payments.aggregate(
            total=Sum('base_currency_amount')
        )['total'] or Decimal('0.00')
        
        # Get overdue invoices
        overdue_invoices = invoices.filter(
            due_date__lt=date.today(),
            status__in=['OPEN', 'SENT', 'VIEWED', 'PARTIAL'],
            amount_due__gt=0
        )
        
        overdue_amount = overdue_invoices.aggregate(
            total=Sum('base_currency_amount_due')
        )['total'] or Decimal('0.00')
        
        return {
            'customer_id': customer_id,
            'customer_name': customer.name,
            'financial_profile': {
                'credit_limit': float(profile.credit_limit),
                'credit_rating': profile.credit_rating,
                'payment_terms_days': profile.payment_terms_days,
                'current_balance': float(profile.current_balance),
                'credit_utilization': float(profile.calculate_credit_utilization()),
                'risk_level': profile.risk_level,
                'collection_priority': profile.collection_priority,
                'payment_history_score': profile.payment_history_score,
                'average_days_to_pay': float(profile.average_days_to_pay),
                'last_payment_date': profile.last_payment_date
            },
            'period_summary': {
                'period_days': days,
                'total_sales': float(period_sales),
                'total_payments': float(period_payments),
                'invoice_count': invoices.count(),
                'payment_count': payments.count(),
                'average_invoice_amount': float(period_sales / invoices.count()) if invoices.count() > 0 else 0
            },
            'outstanding_summary': {
                'total_outstanding': float(profile.current_balance),
                'overdue_amount': float(overdue_amount),
                'overdue_invoices': overdue_invoices.count(),
                'largest_invoice': float(invoices.aggregate(
                    max_amount=Max('base_currency_total')
                )['max_amount'] or 0),
                'oldest_invoice_days': (
                    date.today() - invoices.filter(
                        status__in=['OPEN', 'SENT', 'VIEWED', 'PARTIAL']
                    ).aggregate(
                        oldest=Min('invoice_date')
                    )['oldest']
                ).days if invoices.filter(
                    status__in=['OPEN', 'SENT', 'VIEWED', 'PARTIAL']
                ).exists() else 0
            }
        }

    def get_customer_ranking(self, metric: str = 'total_sales', period_days: int = 365) -> List[Dict]:
        """Get customer ranking by specified metric"""
        
        cutoff_date = date.today() - timedelta(days=period_days)
        
        if metric == 'total_sales':
            ranking = Customer.objects.filter(
                tenant=self.tenant
            ).annotate(
                metric_value=Sum(
                    'invoices__base_currency_total',
                    filter=Q(invoices__invoice_date__gte=cutoff_date)
                )
            ).order_by('-metric_value')
            
        elif metric == 'total_payments':
            ranking = Customer.objects.filter(
                tenant=self.tenant
            ).annotate(
                metric_value=Sum(
                    'payments__base_currency_amount',
                    filter=Q(
                        payments__payment_date__gte=cutoff_date,
                        payments__payment_type='RECEIVED'
                    )
                )
            ).order_by('-metric_value')
            
        elif metric == 'outstanding_balance':
            ranking = Customer.objects.filter(
                tenant=self.tenant
            ).annotate(
                metric_value=Sum(
                    'invoices__base_currency_amount_due',
                    filter=Q(
                        invoices__status__in=['OPEN', 'SENT', 'VIEWED', 'PARTIAL'],
                        invoices__amount_due__gt=0
                    )
                )
            ).order_by('-metric_value')
            
        else:
            raise ValueError(f"Unknown metric: {metric}")
        
        result = []
        for rank, customer in enumerate(ranking[:50], 1):  # Top 50
            result.append({
                'rank': rank,
                'customer_id': customer.id,
                'customer_name': customer.name,
                'metric_value': float(customer.metric_value or 0),
                'metric_name': metric
            })
        
        return result