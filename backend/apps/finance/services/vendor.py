# backend/apps/finance/services/vendor.py
"""
Vendor Service
Handles vendor management, performance tracking, payment history, and vendor analytics
"""

from typing import Dict, List, Optional, Any, Tuple
from decimal import Decimal
from datetime import date, datetime, timedelta
from django.db import transaction, models
from django.db.models import Sum, Avg, Count, Q, F, Case, When, Max, Min
from django.core.exceptions import ValidationError
from django.utils import timezone
import statistics
import logging

from .base import FinanceBaseService, ServiceResult
from ..models import Vendor, VendorContact, Bill, Payment, PaymentApplication, Currency

logger = logging.getLogger(__name__)


class VendorService(FinanceBaseService):
    """
    Comprehensive vendor management and analytics service
    """
    
    def get_service_name(self) -> str:
        return "VendorService"
    
    @transaction.atomic
    def create_vendor(self, vendor_data: Dict[str, Any]) -> ServiceResult:
        """
        Create a new vendor with validation and setup
        
        Args:
            vendor_data: Dictionary containing vendor information
                Required fields:
                - company_name: str
                - email: str
                Optional fields:
                - vendor_type: str
                - payment_terms: str
                - credit_limit: Decimal
                - currency_code: str
                - addresses: Dict
                - contacts: List[Dict]
                
        Returns:
            ServiceResult with vendor information
        """
        def _create_vendor():
            # Validate required fields
            required_fields = ['company_name']
            for field in required_fields:
                if field not in vendor_data:
                    raise ValidationError(f"Required field '{field}' is missing")
            
            # Check for duplicate vendors
            company_name = vendor_data['company_name'].strip()
            if Vendor.objects.filter(
                tenant=self.tenant,
                company_name__iexact=company_name
            ).exists():
                raise ValidationError(f"Vendor with company name '{company_name}' already exists")
            
            # Get currency
            currency_code = vendor_data.get('currency_code', self.base_currency.code)
            try:
                currency = Currency.objects.get(tenant=self.tenant, code=currency_code)
            except Currency.DoesNotExist:
                raise ValidationError(f"Currency '{currency_code}' not found")
            
            # Create vendor
            vendor = Vendor.objects.create(
                tenant=self.tenant,
                company_name=company_name,
                display_name=vendor_data.get('display_name', company_name),
                vendor_type=vendor_data.get('vendor_type', 'SUPPLIER'),
                email=vendor_data.get('email', ''),
                phone=vendor_data.get('phone', ''),
                mobile=vendor_data.get('mobile', ''),
                fax=vendor_data.get('fax', ''),
                website=vendor_data.get('website', ''),
                payment_terms=vendor_data.get('payment_terms', 'NET_30'),
                payment_terms_days=vendor_data.get('payment_terms_days', 30),
                credit_limit=Decimal(str(vendor_data.get('credit_limit', '0.00'))),
                currency=currency,
                tax_id=vendor_data.get('tax_id', ''),
                vat_number=vendor_data.get('vat_number', ''),
                is_tax_exempt=vendor_data.get('is_tax_exempt', False),
                tax_exempt_number=vendor_data.get('tax_exempt_number', ''),
                is_1099_vendor=vendor_data.get('is_1099_vendor', False),
                bank_name=vendor_data.get('bank_name', ''),
                bank_account_number=vendor_data.get('bank_account_number', ''),
                routing_number=vendor_data.get('routing_number', ''),
                swift_code=vendor_data.get('swift_code', ''),
                iban=vendor_data.get('iban', ''),
                is_inventory_supplier=vendor_data.get('is_inventory_supplier', False),
                supplier_code=vendor_data.get('supplier_code', ''),
                notes=vendor_data.get('notes', ''),
                internal_notes=vendor_data.get('internal_notes', ''),
                status='ACTIVE'
            )
            
            # Set addresses
            if 'billing_address' in vendor_data:
                vendor.billing_address = vendor_data['billing_address']
            
            if 'shipping_address' in vendor_data:
                vendor.shipping_address = vendor_data['shipping_address']
            
            if 'remit_to_address' in vendor_data:
                vendor.remit_to_address = vendor_data['remit_to_address']
            
            vendor.save()
            
            # Create contacts if provided
            contacts_created = []
            if 'contacts' in vendor_data:
                for contact_data in vendor_data['contacts']:
                    contact = self._create_vendor_contact(vendor, contact_data)
                    contacts_created.append({
                        'contact_id': contact.id,
                        'name': f"{contact.first_name} {contact.last_name}",
                        'email': contact.email,
                        'contact_type': contact.contact_type
                    })
            
            # Set default accounts if provided
            if 'default_expense_account_id' in vendor_data:
                try:
                    expense_account = Account.objects.get(
                        id=vendor_data['default_expense_account_id'],
                        tenant=self.tenant
                    )
                    vendor.default_expense_account = expense_account
                    vendor.save()
                except Account.DoesNotExist:
                    pass  # Skip if account not found
            
            return {
                'vendor_id': vendor.id,
                'vendor_number': vendor.vendor_number,
                'company_name': vendor.company_name,
                'display_name': vendor.display_name,
                'vendor_type': vendor.vendor_type,
                'status': vendor.status,
                'currency': vendor.currency.code,
                'payment_terms': vendor.payment_terms,
                'contacts_created': contacts_created,
                'is_inventory_supplier': vendor.is_inventory_supplier
            }
        
        return self.safe_execute("create_vendor", _create_vendor)
    
    def _create_vendor_contact(self, vendor: Vendor, contact_data: Dict[str, Any]) -> VendorContact:
        """Create a vendor contact"""
        
        return VendorContact.objects.create(
            tenant=self.tenant,
            vendor=vendor,
            contact_type=contact_data.get('contact_type', 'OTHER'),
            first_name=contact_data.get('first_name', ''),
            last_name=contact_data.get('last_name', ''),
            title=contact_data.get('title', ''),
            email=contact_data.get('email', ''),
            phone=contact_data.get('phone', ''),
            mobile=contact_data.get('mobile', ''),
            is_primary=contact_data.get('is_primary', False),
            receive_communications=contact_data.get('receive_communications', True)
        )
    
    def get_vendor_balance(self, vendor_id: int, as_of_date: Optional[date] = None) -> ServiceResult:
        """
        Get current balance for a vendor (amount owed to vendor)
        
        Args:
            vendor_id: ID of vendor
            as_of_date: Date to calculate balance as of
            
        Returns:
            ServiceResult with balance information
        """
        def _get_vendor_balance():
            try:
                vendor = Vendor.objects.get(id=vendor_id, tenant=self.tenant)
            except Vendor.DoesNotExist:
                raise ValidationError(f"Vendor with ID {vendor_id} not found")
            
            if as_of_date is None:
                as_of_date = timezone.now().date()
            
            # Get outstanding bills
            outstanding_bills = Bill.objects.filter(
                tenant=self.tenant,
                vendor=vendor,
                status__in=['OPEN', 'APPROVED', 'PARTIAL'],
                bill_date__lte=as_of_date
            )
            
            total_outstanding = outstanding_bills.aggregate(
                total=Sum('base_currency_amount_due')
            )['total'] or Decimal('0.00')
            
            # Get bill details
            bill_details = []
            for bill in outstanding_bills.order_by('due_date'):
                days_since_due = (as_of_date - bill.due_date).days
                
                bill_details.append({
                    'bill_id': bill.id,
                    'bill_number': bill.bill_number,
                    'bill_date': bill.bill_date.isoformat(),
                    'due_date': bill.due_date.isoformat(),
                    'original_amount': bill.base_currency_total,
                    'amount_due': bill.base_currency_amount_due,
                    'days_since_due': max(0, days_since_due),
                    'status': bill.status,
                    'vendor_invoice_number': bill.vendor_invoice_number
                })
            
            # Calculate aging
            aging_buckets = {
                'current': Decimal('0.00'),
                '1_30_days': Decimal('0.00'),
                '31_60_days': Decimal('0.00'),
                '61_90_days': Decimal('0.00'),
                'over_90_days': Decimal('0.00')
            }
            
            for bill in outstanding_bills:
                days_since_due = (as_of_date - bill.due_date).days
                amount = bill.base_currency_amount_due
                
                if days_since_due <= 0:
                    aging_buckets['current'] += amount
                elif days_since_due <= 30:
                    aging_buckets['1_30_days'] += amount
                elif days_since_due <= 60:
                    aging_buckets['31_60_days'] += amount
                elif days_since_due <= 90:
                    aging_buckets['61_90_days'] += amount
                else:
                    aging_buckets['over_90_days'] += amount
            
            return {
                'vendor_id': vendor_id,
                'vendor_name': vendor.company_name,
                'as_of_date': as_of_date.isoformat(),
                'total_outstanding': total_outstanding,
                'base_currency': self.base_currency.code,
                'bill_count': outstanding_bills.count(),
                'aging_buckets': aging_buckets,
                'bill_details': bill_details
            }
        
        return self.safe_execute("get_vendor_balance", _get_vendor_balance)
    
    def get_vendor_payment_history(self, vendor_id: int, 
                                 start_date: Optional[date] = None,
                                 end_date: Optional[date] = None) -> ServiceResult:
        """
        Get payment history for a vendor
        
        Args:
            vendor_id: ID of vendor
            start_date: Start date for history
            end_date: End date for history
            
        Returns:
            ServiceResult with payment history
        """
        def _get_payment_history():
            try:
                vendor = Vendor.objects.get(id=vendor_id, tenant=self.tenant)
            except Vendor.DoesNotExist:
                raise ValidationError(f"Vendor with ID {vendor_id} not found")
            
            if end_date is None:
                end_date = timezone.now().date()
            
            if start_date is None:
                start_date = end_date - timedelta(days=365)  # Default to 1 year
            
            # Get payments made to this vendor
            payments = Payment.objects.filter(
                tenant=self.tenant,
                vendor=vendor,
                payment_type='MADE',
                payment_date__range=[start_date, end_date]
            ).order_by('-payment_date')
            
            payment_history = []
            total_payments = Decimal('0.00')
            
            for payment in payments:
                # Get bills this payment was applied to
                applications = PaymentApplication.objects.filter(
                    payment=payment,
                    bill__isnull=False
                ).select_related('bill')
                
                applied_to_bills = []
                for app in applications:
                    applied_to_bills.append({
                        'bill_id': app.bill.id,
                        'bill_number': app.bill.bill_number,
                        'amount_applied': app.amount_applied,
                        'discount_amount': app.discount_amount
                    })
                
                payment_history.append({
                    'payment_id': payment.id,
                    'payment_number': payment.payment_number,
                    'payment_date': payment.payment_date.isoformat(),
                    'amount': payment.base_currency_amount,
                    'payment_method': payment.payment_method,
                    'reference_number': payment.reference_number,
                    'check_number': payment.check_number,
                    'status': payment.status,
                    'applied_to_bills': applied_to_bills,
                    'notes': payment.notes
                })
                
                total_payments += payment.base_currency_amount
            
            # Calculate payment statistics
            if payments.exists():
                payment_amounts = [float(p.base_currency_amount) for p in payments]
                statistics_data = {
                    'average_payment': statistics.mean(payment_amounts),
                    'largest_payment': max(payment_amounts),
                    'smallest_payment': min(payment_amounts),
                    'payment_frequency': len(payment_amounts) / ((end_date - start_date).days / 30.44)  # payments per month
                }
            else:
                statistics_data = None
            
            return {
                'vendor_id': vendor_id,
                'vendor_name': vendor.company_name,
                'date_range': {
                    'start_date': start_date.isoformat(),
                    'end_date': end_date.isoformat()
                },
                'total_payments': total_payments,
                'payment_count': payments.count(),
                'base_currency': self.base_currency.code,
                'payment_history': payment_history,
                'statistics': statistics_data
            }
        
        return self.safe_execute("get_vendor_payment_history", _get_payment_history)
    
    def calculate_vendor_performance_metrics(self, vendor_id: int) -> ServiceResult:
        """
        Calculate comprehensive vendor performance metrics
        
        Args:
            vendor_id: ID of vendor
            
        Returns:
            ServiceResult with performance metrics
        """
        def _calculate_performance():
            try:
                vendor = Vendor.objects.get(id=vendor_id, tenant=self.tenant)
            except Vendor.DoesNotExist:
                raise ValidationError(f"Vendor with ID {vendor_id} not found")
            
            # Calculate metrics for last 12 months
            end_date = timezone.now().date()
            start_date = end_date - timedelta(days=365)
            
            # Bills in the period
            bills = Bill.objects.filter(
                tenant=self.tenant,
                vendor=vendor,
                bill_date__range=[start_date, end_date]
            )
            
            if not bills.exists():
                return {
                    'vendor_id': vendor_id,
                    'vendor_name': vendor.company_name,
                    'message': 'No bills found in the last 12 months',
                    'metrics': None
                }
            
            # Payment timing analysis
            paid_bills = bills.filter(status='PAID')
            payment_days = []
            
            for bill in paid_bills:
                last_payment = Payment.objects.filter(
                    tenant=self.tenant,
                    applications__bill=bill
                ).order_by('-payment_date').first()
                
                if last_payment:
                    days_to_pay = (last_payment.payment_date - bill.bill_date).days
                    payment_days.append(days_to_pay)
            
            # Financial metrics
            total_spend = bills.aggregate(
                total=Sum('base_currency_total')
            )['total'] or Decimal('0.00')
            
            average_bill_amount = bills.aggregate(
                avg=Avg('base_currency_total')
            )['avg'] or Decimal('0.00')
            
            # Payment performance
            if payment_days:
                avg_payment_days = statistics.mean(payment_days)
                on_time_payments = len([days for days in payment_days if days <= vendor.payment_terms_days])
                on_time_rate = (on_time_payments / len(payment_days)) * 100
            else:
                avg_payment_days = 0
                on_time_rate = 0
            
            # Bill frequency analysis
            bill_frequency = bills.count() / 12  # bills per month
            
            # Status distribution
            status_distribution = bills.values('status').annotate(
                count=Count('id'),
                total_amount=Sum('base_currency_total')
            )
            
            # Monthly trend analysis
            monthly_data = []
            for i in range(12):
                month_start = start_date.replace(day=1) + timedelta(days=30 * i)
                month_end = (month_start + timedelta(days=32)).replace(day=1) - timedelta(days=1)
                month_end = min(month_end, end_date)
                
                month_bills = bills.filter(bill_date__range=[month_start, month_end])
                month_total = month_bills.aggregate(
                    total=Sum('base_currency_total')
                )['total'] or Decimal('0.00')
                
                monthly_data.append({
                    'month': month_start.strftime('%Y-%m'),
                    'bill_count': month_bills.count(),
                    'total_amount': month_total
                })
            
            # Quality score calculation (0-100)
            quality_score = 100
            
            # Deduct points for late payments
            if on_time_rate < 90:
                quality_score -= (90 - on_time_rate) * 0.5
            
            # Deduct points for disputed bills
            disputed_bills = bills.filter(status__in=['DISPUTED', 'ON_HOLD']).count()
            if disputed_bills > 0:
                dispute_rate = (disputed_bills / bills.count()) * 100
                quality_score -= dispute_rate * 2
            
            quality_score = max(0, min(100, quality_score))
            
            # Update vendor performance fields
            vendor.average_payment_days = Decimal(str(avg_payment_days))
            vendor.on_time_delivery_rate = Decimal(str(on_time_rate))
            vendor.quality_rating = Decimal(str(quality_score))
            vendor.save(update_fields=['average_payment_days', 'on_time_delivery_rate', 'quality_rating'])
            
            return {
                'vendor_id': vendor_id,
                'vendor_name': vendor.company_name,
                'analysis_period': {
                    'start_date': start_date.isoformat(),
                    'end_date': end_date.isoformat()
                },
                'financial_metrics': {
                    'total_spend': total_spend,
                    'average_bill_amount': average_bill_amount,
                    'bill_count': bills.count(),
                    'bill_frequency_per_month': bill_frequency
                },
                'payment_performance': {
                    'average_payment_days': avg_payment_days,
                    'on_time_payment_rate': on_time_rate,
                    'target_payment_terms': vendor.payment_terms_days,
                    'paid_bills_analyzed': len(payment_days)
                },
                'quality_metrics': {
                    'quality_score': quality_score,
                    'disputed_bills': disputed_bills,
                    'dispute_rate': (disputed_bills / bills.count()) * 100 if bills.count() > 0 else 0
                },
                'status_distribution': list(status_distribution),
                'monthly_trends': monthly_data,
                'base_currency': self.base_currency.code
            }
        
        return self.safe_execute("calculate_vendor_performance_metrics", _calculate_performance)
    
    def get_vendor_spending_analysis(self, start_date: Optional[date] = None,
                                   end_date: Optional[date] = None,
                                   top_n: int = 10) -> ServiceResult:
        """
        Get spending analysis across all vendors
        
        Args:
            start_date: Start date for analysis
            end_date: End date for analysis
            top_n: Number of top vendors to include
            
        Returns:
            ServiceResult with spending analysis
        """
        def _get_spending_analysis():
            if end_date is None:
                end_date = timezone.now().date()
            
            if start_date is None:
                start_date = end_date - timedelta(days=365)  # Default to 1 year
            
            # Get vendor spending data
            vendor_spending = Bill.objects.filter(
                tenant=self.tenant,
                bill_date__range=[start_date, end_date],
                status__in=['PAID', 'PARTIAL', 'OPEN', 'APPROVED']
            ).values(
                'vendor__id',
                'vendor__company_name',
                'vendor__vendor_type'
            ).annotate(
                total_spend=Sum('base_currency_total'),
                bill_count=Count('id'),
                average_bill_amount=Avg('base_currency_total'),
                last_bill_date=Max('bill_date'),
                first_bill_date=Min('bill_date')
            ).order_by('-total_spend')[:top_n]
            
            # Calculate totals
            total_spending = sum(vendor['total_spend'] for vendor in vendor_spending)
            total_bills = sum(vendor['bill_count'] for vendor in vendor_spending)
            
            # Add percentage and running totals
            running_total = Decimal('0.00')
            vendor_analysis = []
            
            for i, vendor in enumerate(vendor_spending):
                vendor_total = vendor['total_spend']
                running_total += vendor_total
                
                vendor_analysis.append({
                    'rank': i + 1,
                    'vendor_id': vendor['vendor__id'],
                    'vendor_name': vendor['vendor__company_name'],
                    'vendor_type': vendor['vendor__vendor_type'],
                    'total_spend': vendor_total,
                    'bill_count': vendor['bill_count'],
                    'average_bill_amount': vendor['average_bill_amount'],
                    'percentage_of_total': (vendor_total / total_spending * 100) if total_spending > 0 else 0,
                    'cumulative_percentage': (running_total / total_spending * 100) if total_spending > 0 else 0,
                    'first_bill_date': vendor['first_bill_date'].isoformat() if vendor['first_bill_date'] else None,
                    'last_bill_date': vendor['last_bill_date'].isoformat() if vendor['last_bill_date'] else None
                })
            
            # Spending by vendor type
            type_spending = Bill.objects.filter(
                tenant=self.tenant,
                bill_date__range=[start_date, end_date],
                status__in=['PAID', 'PARTIAL', 'OPEN', 'APPROVED']
            ).values('vendor__vendor_type').annotate(
                total_spend=Sum('base_currency_total'),
                vendor_count=Count('vendor', distinct=True),
                bill_count=Count('id')
            ).order_by('-total_spend')
            
            # Monthly spending trends
            monthly_spending = []
            current_date = start_date.replace(day=1)
            
            while current_date <= end_date:
                month_end = current_date.replace(
                    day=calendar.monthrange(current_date.year, current_date.month)[1]
                )
                month_end = min(month_end, end_date)
                
                month_total = Bill.objects.filter(
                    tenant=self.tenant,
                    bill_date__range=[current_date, month_end],
                    status__in=['PAID', 'PARTIAL', 'OPEN', 'APPROVED']
                ).aggregate(total=Sum('base_currency_total'))['total'] or Decimal('0.00')
                
                monthly_spending.append({
                    'month': current_date.strftime('%Y-%m'),
                    'total_spend': month_total
                })
                
                # Move to next month
                if current_date.month == 12:
                    current_date = current_date.replace(year=current_date.year + 1, month=1)
                else:
                    current_date = current_date.replace(month=current_date.month + 1)
            
            return {
                'analysis_period': {
                    'start_date': start_date.isoformat(),
                    'end_date': end_date.isoformat()
                },
                'summary': {
                    'total_spending': total_spending,
                    'total_bills': total_bills,
                    'unique_vendors': len(vendor_analysis),
                    'average_bill_amount': total_spending / total_bills if total_bills > 0 else Decimal('0.00'),
                    'top_vendor_concentration': vendor_analysis[0]['percentage_of_total'] if vendor_analysis else 0,
                    'top_5_concentration': sum(v['percentage_of_total'] for v in vendor_analysis[:5])
                },
                'top_vendors': vendor_analysis,
                'spending_by_type': list(type_spending),
                'monthly_trends': monthly_spending,
                'base_currency': self.base_currency.code
            }
        
        return self.safe_execute("get_vendor_spending_analysis", _get_spending_analysis)
    
    def identify_vendor_savings_opportunities(self) -> ServiceResult:
        """
        Identify potential cost savings opportunities with vendors
        
        Returns:
            ServiceResult with savings opportunities
        """
        def _identify_savings_opportunities():
            opportunities = []
            
            # Get vendor data for analysis
            vendors = Vendor.objects.filter(
                tenant=self.tenant,
                status='ACTIVE'
            ).annotate(
                total_spend_12m=Sum(
                    'bills__base_currency_total',
                    filter=Q(
                        bills__bill_date__gte=timezone.now().date() - timedelta(days=365),
                        bills__status__in=['PAID', 'PARTIAL', 'OPEN', 'APPROVED']
                    )
                ),
                bill_count_12m=Count(
                    'bills',
                    filter=Q(
                        bills__bill_date__gte=timezone.now().date() - timedelta(days=365),
                        bills__status__in=['PAID', 'PARTIAL', 'OPEN', 'APPROVED']
                    )
                ),
                avg_payment_delay=Avg(
                    F('bills__applications__payment__payment_date') - F('bills__due_date'),
                    filter=Q(
                        bills__status='PAID',
                        bills__bill_date__gte=timezone.now().date() - timedelta(days=365)
                    )
                )
            )
            
            for vendor in vendors:
                if not vendor.total_spend_12m:
                    continue
                
                vendor_opportunities = []
                
                # High spend vendors - negotiate better terms
                if vendor.total_spend_12m > 50000:  # Configurable threshold
                    vendor_opportunities.append({
                        'type': 'volume_discount',
                        'description': f'High annual spend of {self.format_currency(vendor.total_spend_12m)} - negotiate volume discounts',
                        'potential_savings': vendor.total_spend_12m * Decimal('0.02'),  # 2% potential savings
                        'priority': 'high',
                        'action': 'Renegotiate contract terms for volume pricing'
                    })
                
                # Frequent small bills - consolidate
                if vendor.bill_count_12m > 24 and vendor.total_spend_12m / vendor.bill_count_12m < 1000:
                    avg_bill = vendor.total_spend_12m / vendor.bill_count_12m
                    vendor_opportunities.append({
                        'type': 'consolidation',
                        'description': f'Frequent small bills (avg {self.format_currency(avg_bill)}) - consolidate orders',
                        'potential_savings': vendor.bill_count_12m * Decimal('25'),  # Processing cost savings
                        'priority': 'medium',
                        'action': 'Set up consolidated billing or minimum order amounts'
                    })
                
                # Early payment discounts
                if (vendor.payment_terms_days >= 30 and 
                    vendor.avg_payment_delay and 
                    vendor.avg_payment_delay.days < 15):
                    
                    potential_discount = vendor.total_spend_12m * Decimal('0.01')  # 1% early payment discount
                    vendor_opportunities.append({
                        'type': 'early_payment',
                        'description': f'Consistently pay early - negotiate early payment discounts',
                        'potential_savings': potential_discount,
                        'priority': 'medium',
                        'action': 'Negotiate 1-2% discount for payments within 10 days'
                    })
                
                # Poor performance vendors
                if (hasattr(vendor, 'quality_rating') and 
                    vendor.quality_rating < 70):
                    
                    vendor_opportunities.append({
                        'type': 'quality_improvement',
                        'description': f'Poor performance score ({vendor.quality_rating}) - review vendor relationship',
                        'potential_savings': vendor.total_spend_12m * Decimal('0.05'),  # Risk reduction
                        'priority': 'high',
                        'action': 'Review vendor performance and consider alternatives'
                    })
                
                if vendor_opportunities:
                    total_potential = sum(opp['potential_savings'] for opp in vendor_opportunities)
                    opportunities.append({
                        'vendor_id': vendor.id,
                        'vendor_name': vendor.company_name,
                        'annual_spend': vendor.total_spend_12m,
                        'opportunities': vendor_opportunities,
                        'total_potential_savings': total_potential,
                        'roi_percentage': (total_potential / vendor.total_spend_12m * 100) if vendor.total_spend_12m > 0 else 0
                    })
            
            # Sort by potential savings
            opportunities.sort(key=lambda x: x['total_potential_savings'], reverse=True)
            
            # Calculate summary
            total_potential_savings = sum(opp['total_potential_savings'] for opp in opportunities)
            total_analyzed_spend = sum(opp['annual_spend'] for opp in opportunities)
            
            return {
                'analysis_date': timezone.now().date().isoformat(),
                'summary': {
                    'vendors_analyzed': len(opportunities),
                    'total_potential_savings': total_potential_savings,
                    'total_analyzed_spend': total_analyzed_spend,
                    'overall_savings_percentage': (total_potential_savings / total_analyzed_spend * 100) if total_analyzed_spend > 0 else 0
                },
                'opportunities': opportunities[:20],  # Top 20 opportunities
                'base_currency': self.base_currency.code
            }
        
        return self.safe_execute("identify_vendor_savings_opportunities", _identify_savings_opportunities)