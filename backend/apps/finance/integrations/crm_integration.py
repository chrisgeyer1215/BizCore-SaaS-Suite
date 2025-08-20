# backend/apps/finance/integrations/crm_integration.py

"""
Finance-CRM Integration Service
Handles customer financial profiles, credit management, and sales analytics
"""

from django.db import transaction
from django.utils import timezone
from decimal import Decimal
from datetime import date, timedelta
from ..models import CustomerFinancialProfile, Invoice, Payment

class CRMIntegrationService:
    """Service for finance-CRM integration"""
    
    def __init__(self, tenant):
        self.tenant = tenant
    
    @transaction.atomic
    def sync_customer_profiles(self, customer_ids=None):
        """Sync customer financial profiles"""
        from apps.crm.models import Customer
        
        customers = Customer.objects.filter(tenant=self.tenant)
        if customer_ids:
            customers = customers.filter(id__in=customer_ids)
        
        sync_results = []
        
        for customer in customers:
            try:
                # Get or create financial profile
                profile, created = CustomerFinancialProfile.objects.get_or_create(
                    customer=customer,
                    tenant=self.tenant,
                    defaults={
                        'credit_limit': Decimal('5000.00'),
                        'payment_terms_days': 30,
                        'credit_rating': 'UNRATED'
                    }
                )
                
                # Calculate financial metrics
                self.update_customer_financial_metrics(customer, profile)
                
                sync_results.append({
                    'customer_id': customer.id,
                    'customer_name': customer.name,
                    'profile_created': created,
                    'current_balance': profile.current_balance,
                    'credit_utilization': profile.calculate_credit_utilization(),
                    'status': 'success'
                })
                
            except Exception as e:
                sync_results.append({
                    'customer_id': customer.id,
                    'customer_name': customer.name,
                    'error': str(e),
                    'status': 'error'
                })
        
        return sync_results
    
    def update_customer_financial_metrics(self, customer, profile):
        """Update customer financial metrics"""
        # Calculate current balance (total outstanding invoices)
        outstanding_invoices = Invoice.objects.filter(
            customer=customer,
            tenant=self.tenant,
            status__in=['OPEN', 'SENT', 'VIEWED', 'PARTIAL']
        ).aggregate(
            total_outstanding=models.Sum('amount_due')
        )
        
        profile.current_balance = outstanding_invoices['total_outstanding'] or Decimal('0.00')
        
        # Calculate total sales
        total_sales = Invoice.objects.filter(
            customer=customer,
            tenant=self.tenant,
            status__in=['PAID', 'PARTIAL', 'OPEN']
        ).aggregate(
            total=models.Sum('total_amount')
        )
        
        profile.total_sales = total_sales['total'] or Decimal('0.00')
        
        # Calculate total payments
        total_payments = Payment.objects.filter(
            customer=customer,
            tenant=self.tenant,
            payment_type='RECEIVED',
            status='CLEARED'
        ).aggregate(
            total=models.Sum('amount')
        )
        
        profile.total_payments = total_payments['total'] or Decimal('0.00')
        
        # Update highest balance
        if profile.current_balance > profile.highest_balance:
            profile.highest_balance = profile.current_balance
        
        # Calculate average days to pay
        paid_invoices = Invoice.objects.filter(
            customer=customer,
            tenant=self.tenant,
            status='PAID'
        ).exclude(amount_paid=0)
        
        if paid_invoices.exists():
            total_days = 0
            count = 0
            
            for invoice in paid_invoices:
                # Get the last payment date for this invoice
                last_payment = Payment.objects.filter(
                    applications__invoice=invoice,
                    status='CLEARED'
                ).order_by('-payment_date').first()
                
                if last_payment:
                    days_to_pay = (last_payment.payment_date - invoice.invoice_date).days
                    total_days += days_to_pay
                    count += 1
            
            if count > 0:
                profile.average_days_to_pay = Decimal(total_days) / Decimal(count)
        
        # Update last payment date
        last_payment = Payment.objects.filter(
            customer=customer,
            tenant=self.tenant,
            payment_type='RECEIVED',
            status='CLEARED'
        ).order_by('-payment_date').first()
        
        if last_payment:
            profile.last_payment_date = last_payment.payment_date
        
        # Calculate payment history score (0-100)
        profile.payment_history_score = self.calculate_payment_history_score(customer)
        
        # Update risk level
        profile.risk_level = self.calculate_risk_level(profile)
        
        profile.save()
    
    def calculate_payment_history_score(self, customer):
        """Calculate payment history score (0-100)"""
        score = 100  # Start with perfect score
        
        # Get invoices from last 12 months
        twelve_months_ago = date.today() - timedelta(days=365)
        recent_invoices = Invoice.objects.filter(
            customer=customer,
            tenant=self.tenant,
            invoice_date__gte=twelve_months_ago,
            status__in=['PAID', 'PARTIAL', 'OVERDUE']
        )
        
        if not recent_invoices.exists():
            return 50  # Neutral score for new customers
        
        total_invoices = recent_invoices.count()
        overdue_invoices = recent_invoices.filter(
            due_date__lt=date.today(),
            status__in=['OPEN', 'SENT', 'VIEWED', 'PARTIAL']
        ).count()
        
        # Deduct points for overdue invoices
        if total_invoices > 0:
            overdue_percentage = (overdue_invoices / total_invoices) * 100
            score -= overdue_percentage * 0.5  # Deduct 0.5 points per % overdue
        
        # Deduct points for late payments
        late_payments = 0
        for invoice in recent_invoices.filter(status='PAID'):
            last_payment = Payment.objects.filter(
                applications__invoice=invoice,
                status='CLEARED'
            ).order_by('-payment_date').first()
            
            if last_payment and last_payment.payment_date > invoice.due_date:
                days_late = (last_payment.payment_date - invoice.due_date).days
                if days_late > 0:
                    late_payments += 1
                    score -= min(days_late * 0.1, 10)  # Max 10 points per late payment
        
        return max(0, min(100, int(score)))
    
    def calculate_risk_level(self, profile):
        """Calculate customer risk level"""
        risk_score = 0
        
        # Credit utilization risk
        credit_utilization = profile.calculate_credit_utilization()
        if credit_utilization > 90:
            risk_score += 3
        elif credit_utilization > 75:
            risk_score += 2
        elif credit_utilization > 50:
            risk_score += 1
        
        # Payment history risk
        if profile.payment_history_score < 60:
            risk_score += 3
        elif profile.payment_history_score < 80:
            risk_score += 2
        elif profile.payment_history_score < 90:
            risk_score += 1
        
        # Average days to pay risk
        if profile.average_days_to_pay > 60:
            risk_score += 2
        elif profile.average_days_to_pay > 45:
            risk_score += 1
        
        # Current balance risk
        if profile.current_balance > profile.credit_limit:
            risk_score += 3
        
        # Determine risk level
        if risk_score >= 7:
            return 'HIGH'
        elif risk_score >= 4:
            return 'MEDIUM'
        else:
            return 'LOW'
    
    @transaction.atomic
    def update_credit_limits(self, updates):
        """Update customer credit limits"""
        results = []
        
        for update in updates:
            try:
                customer_id = update['customer_id']
                new_credit_limit = Decimal(str(update['credit_limit']))
                reason = update.get('reason', 'Credit limit update')
                
                profile = CustomerFinancialProfile.objects.get(
                    customer_id=customer_id,
                    tenant=self.tenant
                )
                
                old_credit_limit = profile.credit_limit
                profile.credit_limit = new_credit_limit
                profile.save()
                
                # Log credit limit change
                from ..models import CustomerCreditLimitHistory
                CustomerCreditLimitHistory.objects.create(
                    tenant=self.tenant,
                    customer_id=customer_id,
                    previous_limit=old_credit_limit,
                    new_limit=new_credit_limit,
                    changed_date=timezone.now(),
                    reason=reason
                )
                
                results.append({
                    'customer_id': customer_id,
                    'old_limit': old_credit_limit,
                    'new_limit': new_credit_limit,
                    'status': 'success'
                })
                
            except Exception as e:
                results.append({
                    'customer_id': update.get('customer_id'),
                    'error': str(e),
                    'status': 'error'
                })
        
        return results
    
    def generate_customer_statements(self, customer_ids=None, statement_date=None):
        """Generate customer account statements"""
        if not statement_date:
            statement_date = date.today()
        
        from apps.crm.models import Customer
        
        customers = Customer.objects.filter(tenant=self.tenant)
        if customer_ids:
            customers = customers.filter(id__in=customer_ids)
        
        statements = []
        
        for customer in customers:
            # Get customer financial profile
            try:
                profile = customer.financial_profile
            except CustomerFinancialProfile.DoesNotExist:
                continue
            
            # Get outstanding invoices
            outstanding_invoices = Invoice.objects.filter(
                customer=customer,
                tenant=self.tenant,
                status__in=['OPEN', 'SENT', 'VIEWED', 'PARTIAL'],
                amount_due__gt=0
            ).order_by('due_date')
            
            # Get recent payments
            recent_payments = Payment.objects.filter(
                customer=customer,
                tenant=self.tenant,
                payment_type='RECEIVED',
                payment_date__gte=statement_date - timedelta(days=30)
            ).order_by('-payment_date')
            
            # Calculate aging
            aging = self.calculate_customer_aging(customer, statement_date)
            
            statement = {
                'customer_id': customer.id,
                'customer_name': customer.name,
                'statement_date': statement_date,
                'current_balance': profile.current_balance,
                'credit_limit': profile.credit_limit,
                'available_credit': profile.credit_limit - profile.current_balance,
                'outstanding_invoices': [
                    {
                        'invoice_number': inv.invoice_number,
                        'invoice_date': inv.invoice_date,
                        'due_date': inv.due_date,
                        'amount_due': inv.amount_due,
                        'days_overdue': max(0, (statement_date - inv.due_date).days)
                    }
                    for inv in outstanding_invoices
                ],
                'recent_payments': [
                    {
                        'payment_number': pay.payment_number,
                        'payment_date': pay.payment_date,
                        'amount': pay.amount,
                        'payment_method': pay.payment_method
                    }
                    for pay in recent_payments
                ],
                'aging': aging
            }
            
            statements.append(statement)
        
        return statements
    
    def calculate_customer_aging(self, customer, as_of_date=None):
        """Calculate customer aging buckets"""
        if not as_of_date:
            as_of_date = date.today()
        
        outstanding_invoices = Invoice.objects.filter(
            customer=customer,
            tenant=self.tenant,
            status__in=['OPEN', 'SENT', 'VIEWED', 'PARTIAL'],
            amount_due__gt=0
        )
        
        aging = {
            'current': Decimal('0.00'),
            'days_1_30': Decimal('0.00'),
            'days_31_60': Decimal('0.00'),
            'days_61_90': Decimal('0.00'),
            'over_90': Decimal('0.00')
        }
        
        for invoice in outstanding_invoices:
            days_overdue = (as_of_date - invoice.due_date).days
            
            if days_overdue <= 0:
                aging['current'] += invoice.amount_due
            elif days_overdue <= 30:
                aging['days_1_30'] += invoice.amount_due
            elif days_overdue <= 60:
                aging['days_31_60'] += invoice.amount_due
            elif days_overdue <= 90:
                aging['days_61_90'] += invoice.amount_due
            else:
                aging['over_90'] += invoice.amount_due
        
        return aging
    
    def calculate_customer_lifetime_value(self, customer_ids=None):
        """Calculate customer lifetime value"""
        from apps.crm.models import Customer
        
        customers = Customer.objects.filter(tenant=self.tenant)
        if customer_ids:
            customers = customers.filter(id__in=customer_ids)
        
        clv_results = []
        
        for customer in customers:
            # Get customer data for CLV calculation
            invoices = Invoice.objects.filter(
                customer=customer,
                tenant=self.tenant,
                status__in=['PAID', 'PARTIAL']
            ).order_by('invoice_date')
            
            if not invoices.exists():
                continue
            
            # Calculate metrics
            total_revenue = invoices.aggregate(
                total=models.Sum('total_amount')
            )['total'] or Decimal('0.00')
            
            first_invoice_date = invoices.first().invoice_date
            last_invoice_date = invoices.last().invoice_date
            
            # Customer lifespan in months
            lifespan_days = (last_invoice_date - first_invoice_date).days
            lifespan_months = max(1, lifespan_days / 30.44)  # Average days per month
            
            # Average order value
            avg_order_value = total_revenue / invoices.count() if invoices.count() > 0 else Decimal('0.00')
            
            # Purchase frequency (orders per month)
            purchase_frequency = invoices.count() / lifespan_months
            
            # Calculate CLV
            monthly_value = avg_order_value * purchase_frequency
            predicted_lifespan_months = 24  # Default prediction
            
            # Adjust based on payment behavior
            try:
                profile = customer.financial_profile
                if profile.payment_history_score > 80:
                    predicted_lifespan_months = 36
                elif profile.payment_history_score < 60:
                    predicted_lifespan_months = 12
            except CustomerFinancialProfile.DoesNotExist:
                pass
            
            clv = monthly_value * predicted_lifespan_months
            
            clv_results.append({
                'customer_id': customer.id,
                'customer_name': customer.name,
                'total_revenue': total_revenue,
                'avg_order_value': avg_order_value,
                'purchase_frequency': purchase_frequency,
                'lifespan_months': lifespan_months,
                'predicted_lifespan_months': predicted_lifespan_months,
                'monthly_value': monthly_value,
                'customer_lifetime_value': clv
            })
        
        return clv_results