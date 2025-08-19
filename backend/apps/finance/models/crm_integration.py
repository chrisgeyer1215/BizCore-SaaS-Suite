"""
CRM Integration Models
Financial profile integration with CRM customer and lead data
"""

from django.db import models
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.utils import timezone
from decimal import Decimal
from datetime import date, timedelta

from apps.core.models import TenantBaseModel

User = get_user_model()


class CustomerFinancialProfile(TenantBaseModel):
    """Financial profile integration with CRM customer data"""
    
    CREDIT_RATING_CHOICES = [
        ('EXCELLENT', 'Excellent'),
        ('GOOD', 'Good'),
        ('FAIR', 'Fair'),
        ('POOR', 'Poor'),
        ('UNRATED', 'Unrated'),
    ]
    
    RISK_LEVEL_CHOICES = [
        ('LOW', 'Low Risk'),
        ('MEDIUM', 'Medium Risk'),
        ('HIGH', 'High Risk'),
        ('CRITICAL', 'Critical Risk'),
    ]
    
    COLLECTION_PRIORITY_CHOICES = [
        ('LOW', 'Low Priority'),
        ('NORMAL', 'Normal Priority'),
        ('HIGH', 'High Priority'),
        ('URGENT', 'Urgent'),
        ('LEGAL', 'Legal Action'),
    ]
    
    customer = models.OneToOneField(
        'crm.Customer',
        on_delete=models.CASCADE,
        related_name='financial_profile'
    )
    
    # Credit Information
    credit_limit = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    credit_rating = models.CharField(max_length=20, choices=CREDIT_RATING_CHOICES, default='UNRATED')
    credit_check_date = models.DateField(null=True, blank=True)
    credit_notes = models.TextField(blank=True)
    credit_score = models.IntegerField(null=True, blank=True)
    
    # Payment Terms
    payment_terms_days = models.PositiveIntegerField(default=30)
    early_payment_discount = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'))
    late_fee_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'))
    
    # Financial Summary
    total_sales = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    total_payments = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    current_balance = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    highest_balance = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    lifetime_value = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    
    # Payment History
    average_days_to_pay = models.DecimalField(max_digits=5, decimal_places=1, default=Decimal('0.0'))
    payment_history_score = models.IntegerField(default=0)  # 0-100
    last_payment_date = models.DateField(null=True, blank=True)
    last_payment_amount = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    
    # Customer Behavior
    invoice_delivery_method = models.CharField(
        max_length=20,
        choices=[
            ('EMAIL', 'Email'),
            ('MAIL', 'Postal Mail'),
            ('PORTAL', 'Customer Portal'),
            ('FAX', 'Fax'),
        ],
        default='EMAIL'
    )
    preferred_payment_method = models.CharField(
        max_length=20,
        choices=[
            ('CHECK', 'Check'),
            ('CREDIT_CARD', 'Credit Card'),
            ('ACH', 'ACH'),
            ('WIRE', 'Wire Transfer'),
            ('CASH', 'Cash'),
            ('OTHER', 'Other'),
        ],
        blank=True
    )
    
    # Risk Assessment
    risk_level = models.CharField(max_length=20, choices=RISK_LEVEL_CHOICES, default='MEDIUM')
    collection_priority = models.CharField(
        max_length=20,
        choices=COLLECTION_PRIORITY_CHOICES,
        default='NORMAL'
    )
    
    # Account Settings
    account_on_hold = models.BooleanField(default=False)
    require_prepayment = models.BooleanField(default=False)
    auto_send_statements = models.BooleanField(default=True)
    send_payment_reminders = models.BooleanField(default=True)
    
    # Collections Information
    in_collections = models.BooleanField(default=False)
    collections_start_date = models.DateField(null=True, blank=True)
    collections_agency = models.CharField(max_length=200, blank=True)
    
    # Internal Notes
    internal_notes = models.TextField(blank=True)
    collection_notes = models.TextField(blank=True)
    
    # Automated Calculations
    days_sales_outstanding = models.DecimalField(max_digits=5, decimal_places=1, default=Decimal('0.0'))
    payment_trend = models.CharField(
        max_length=20,
        choices=[
            ('IMPROVING', 'Improving'),
            ('STABLE', 'Stable'),
            ('DECLINING', 'Declining'),
        ],
        default='STABLE'
    )
    
    class Meta:
        verbose_name = 'Customer Financial Profile'
        db_table = 'finance_customer_financial_profiles'
        
    def __str__(self):
        return f'{self.customer.name} - Financial Profile'
    
    def clean(self):
        """Validate financial profile"""
        if self.credit_limit < 0:
            raise ValidationError('Credit limit cannot be negative')
        
        if self.credit_score and (self.credit_score < 300 or self.credit_score > 850):
            raise ValidationError('Credit score must be between 300 and 850')
        
        if self.payment_history_score < 0 or self.payment_history_score > 100:
            raise ValidationError('Payment history score must be between 0 and 100')
    
    def update_payment_history(self):
        """Update payment history metrics"""
        from ..services.customer_analytics import CustomerAnalyticsService
        
        service = CustomerAnalyticsService(self.tenant)
        service.update_customer_payment_history(self.customer)
    
    def calculate_credit_utilization(self):
        """Calculate credit utilization percentage"""
        if self.credit_limit > 0:
            return (self.current_balance / self.credit_limit) * 100
        return Decimal('0.00')
    
    def is_over_credit_limit(self):
        """Check if customer is over credit limit"""
        return self.current_balance > self.credit_limit
    
    def get_aging_summary(self):
        """Get accounts receivable aging summary for this customer"""
        from datetime import timedelta
        
        today = date.today()
        aging = {
            'current': Decimal('0.00'),
            '1_30_days': Decimal('0.00'),
            '31_60_days': Decimal('0.00'),
            '61_90_days': Decimal('0.00'),
            'over_90_days': Decimal('0.00')
        }
        
        overdue_invoices = self.customer.invoices.filter(
            status__in=['OPEN', 'SENT', 'VIEWED', 'PARTIAL'],
            due_date__lt=today
        )
        
        for invoice in overdue_invoices:
            days_overdue = (today - invoice.due_date).days
            
            if days_overdue <= 30:
                aging['1_30_days'] += invoice.amount_due
            elif days_overdue <= 60:
                aging['31_60_days'] += invoice.amount_due
            elif days_overdue <= 90:
                aging['61_90_days'] += invoice.amount_due
            else:
                aging['over_90_days'] += invoice.amount_due
        
        # Current (not yet due)
        current_invoices = self.customer.invoices.filter(
            status__in=['OPEN', 'SENT', 'VIEWED', 'PARTIAL'],
            due_date__gte=today
        )
        aging['current'] = current_invoices.aggregate(
            total=models.Sum('amount_due')
        )['total'] or Decimal('0.00')
        
        return aging
    
    def calculate_dso(self):
        """Calculate Days Sales Outstanding"""
        from datetime import timedelta
        
        # Get last 3 months of sales
        three_months_ago = date.today() - timedelta(days=90)
        recent_sales = self.customer.invoices.filter(
            invoice_date__gte=three_months_ago,
            status__in=['OPEN', 'SENT', 'VIEWED', 'PARTIAL', 'PAID']
        ).aggregate(total=models.Sum('total_amount'))['total'] or Decimal('0.00')
        
        if recent_sales > 0:
            average_daily_sales = recent_sales / 90
            if average_daily_sales > 0:
                self.days_sales_outstanding = self.current_balance / average_daily_sales
            else:
                self.days_sales_outstanding = Decimal('0.0')
        else:
            self.days_sales_outstanding = Decimal('0.0')
        
        self.save(update_fields=['days_sales_outstanding'])
    
    def update_risk_assessment(self):
        """Update risk level based on payment history and current status"""
        risk_score = 0
        
        # Payment history score (0-40 points)
        risk_score += (self.payment_history_score * 0.4)
        
        # Credit utilization (0-30 points)
        utilization = self.calculate_credit_utilization()
        if utilization <= 30:
            risk_score += 30
        elif utilization <= 60:
            risk_score += 20
        elif utilization <= 90:
            risk_score += 10
        
        # Days sales outstanding (0-20 points)
        if self.days_sales_outstanding <= 30:
            risk_score += 20
        elif self.days_sales_outstanding <= 45:
            risk_score += 15
        elif self.days_sales_outstanding <= 60:
            risk_score += 10
        elif self.days_sales_outstanding <= 90:
            risk_score += 5
        
        # Account status (0-10 points)
        if not self.account_on_hold and not self.in_collections:
            risk_score += 10
        elif self.account_on_hold:
            risk_score += 5
        
        # Update risk level
        if risk_score >= 80:
            self.risk_level = 'LOW'
        elif risk_score >= 60:
            self.risk_level = 'MEDIUM'
        elif risk_score >= 40:
            self.risk_level = 'HIGH'
        else:
            self.risk_level = 'CRITICAL'
        
        self.save(update_fields=['risk_level'])
    
    @property
    def available_credit(self):
        """Get available credit amount"""
        return max(Decimal('0.00'), self.credit_limit - self.current_balance)
    
    @property
    def overdue_amount(self):
        """Get total overdue amount"""
        today = date.today()
        overdue = self.customer.invoices.filter(
            status__in=['OPEN', 'SENT', 'VIEWED', 'PARTIAL'],
            due_date__lt=today
        ).aggregate(total=models.Sum('amount_due'))['total'] or Decimal('0.00')
        
        return overdue


class LeadFinancialData(TenantBaseModel):
    """Financial data integration for CRM leads"""
    
    BUDGET_STATUS_CHOICES = [
        ('CONFIRMED', 'Budget Confirmed'),
        ('ESTIMATED', 'Estimated Budget'),
        ('UNKNOWN', 'Budget Unknown'),
        ('NO_BUDGET', 'No Budget'),
    ]
    
    DECISION_TIMELINE_CHOICES = [
        ('IMMEDIATE', 'Immediate'),
        ('30_DAYS', 'Within 30 Days'),
        ('60_DAYS', 'Within 60 Days'),
        ('90_DAYS', 'Within 90 Days'),
        ('NEXT_QUARTER', 'Next Quarter'),
        ('NEXT_YEAR', 'Next Year'),
        ('UNKNOWN', 'Unknown'),
    ]
    
    lead = models.OneToOneField(
        'crm.Lead',
        on_delete=models.CASCADE,
        related_name='financial_data'
    )
    
    # Estimated Values
    estimated_annual_revenue = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    estimated_deal_size = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    estimated_gross_margin = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    estimated_lifetime_value = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    
    # Budget Information
    stated_budget = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    budget_status = models.CharField(max_length=20, choices=BUDGET_STATUS_CHOICES, default='UNKNOWN')
    budget_timeframe = models.CharField(max_length=100, blank=True)
    budget_authority = models.CharField(max_length=200, blank=True)
    
    # Decision Making
    decision_maker = models.CharField(max_length=200, blank=True)
    decision_timeline = models.CharField(max_length=20, choices=DECISION_TIMELINE_CHOICES, default='UNKNOWN')
    decision_criteria = models.TextField(blank=True)
    
    # Company Financials
    company_annual_revenue = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    company_size_employees = models.PositiveIntegerField(null=True, blank=True)
    company_funding_stage = models.CharField(
        max_length=20,
        choices=[
            ('STARTUP', 'Startup'),
            ('SERIES_A', 'Series A'),
            ('SERIES_B', 'Series B'),
            ('SERIES_C', 'Series C+'),
            ('IPO', 'Public Company'),
            ('ESTABLISHED', 'Established Private'),
        ],
        blank=True
    )
    
    # Credit & Risk
    credit_check_required = models.BooleanField(default=False)
    credit_check_completed = models.BooleanField(default=False)
    credit_rating = models.CharField(max_length=20, blank=True)
    payment_terms_requested = models.CharField(max_length=100, blank=True)
    
    # Competitive Information
    current_vendor = models.CharField(max_length=200, blank=True)
    current_spend = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    switching_cost = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    
    # Proposal Information
    proposal_value = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    proposal_margin = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    win_probability = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    
    # Timeline
    first_contact_date = models.DateField(null=True, blank=True)
    last_financial_discussion = models.DateField(null=True, blank=True)
    expected_close_date = models.DateField(null=True, blank=True)
    
    # Notes
    financial_notes = models.TextField(blank=True)
    internal_notes = models.TextField(blank=True)
    
    class Meta:
        verbose_name = 'Lead Financial Data'
        db_table = 'finance_lead_financial_data'
        
    def __str__(self):
        return f'{self.lead.company_name} - Financial Data'
    
    def clean(self):
        """Validate lead financial data"""
        if self.estimated_gross_margin and (self.estimated_gross_margin < 0 or self.estimated_gross_margin > 100):
            raise ValidationError('Gross margin must be between 0 and 100 percent')
        
        if self.win_probability and (self.win_probability < 0 or self.win_probability > 100):
            raise ValidationError('Win probability must be between 0 and 100 percent')
        
        if self.proposal_margin and (self.proposal_margin < 0 or self.proposal_margin > 100):
            raise ValidationError('Proposal margin must be between 0 and 100 percent')
    
    @property
    def qualified_budget(self):
        """Check if lead has qualified budget"""
        return self.budget_status in ['CONFIRMED', 'ESTIMATED'] and self.stated_budget
    
    @property
    def weighted_deal_value(self):
        """Calculate weighted deal value based on win probability"""
        if self.proposal_value and self.win_probability:
            return self.proposal_value * (self.win_probability / 100)
        return Decimal('0.00')
    
    @property
    def days_in_pipeline(self):
        """Calculate days since first contact"""
        if self.first_contact_date:
            return (date.today() - self.first_contact_date).days
        return 0
    
    def calculate_lead_score(self):
        """Calculate financial lead score"""
        score = 0
        
        # Budget qualification (0-30 points)
        if self.budget_status == 'CONFIRMED':
            score += 30
        elif self.budget_status == 'ESTIMATED':
            score += 20
        elif self.budget_status == 'UNKNOWN':
            score += 10
        
        # Decision timeline (0-25 points)
        timeline_scores = {
            'IMMEDIATE': 25,
            '30_DAYS': 20,
            '60_DAYS': 15,
            '90_DAYS': 10,
            'NEXT_QUARTER': 5,
            'NEXT_YEAR': 2,
            'UNKNOWN': 0
        }
        score += timeline_scores.get(self.decision_timeline, 0)
        
        # Deal size relative to average (0-25 points)
        if self.proposal_value:
            # This would need to be compared to tenant's average deal size
            if self.proposal_value >= 100000:
                score += 25
            elif self.proposal_value >= 50000:
                score += 20
            elif self.proposal_value >= 25000:
                score += 15
            elif self.proposal_value >= 10000:
                score += 10
            else:
                score += 5
        
        # Win probability (0-20 points)
        if self.win_probability:
            score += int(self.win_probability * 0.2)
        
        return min(100, score)
    
    def update_from_opportunity_won(self, opportunity):
        """Update financial data when opportunity is won"""
        # This would be called when a lead converts to a customer
        # and an opportunity is marked as won
        
        self.proposal_value = opportunity.value
        self.win_probability = Decimal('100.00')
        self.expected_close_date = opportunity.close_date
        
        # Create customer financial profile
        if hasattr(opportunity, 'customer'):
            customer_profile, created = CustomerFinancialProfile.objects.get_or_create(
                tenant=self.tenant,
                customer=opportunity.customer,
                defaults={
                    'credit_limit': self.stated_budget or Decimal('0.00'),
                    'payment_terms_days': 30,
                    'lifetime_value': self.estimated_lifetime_value or Decimal('0.00'),
                }
            )
        
        self.save()


class CustomerCreditApplication(TenantBaseModel):
    """Credit applications for customers requesting credit terms"""
    
    STATUS_CHOICES = [
        ('PENDING', 'Pending Review'),
        ('UNDER_REVIEW', 'Under Review'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
        ('NEEDS_MORE_INFO', 'Needs More Information'),
    ]
    
    customer = models.ForeignKey(
        'crm.Customer',
        on_delete=models.CASCADE,
        related_name='credit_applications'
    )
    
    # Application Information
    application_date = models.DateField(auto_now_add=True)
    requested_credit_limit = models.DecimalField(max_digits=15, decimal_places=2)
    requested_payment_terms = models.CharField(max_length=100)
    
    # Company Information
    business_name = models.CharField(max_length=200)
    business_type = models.CharField(max_length=100)
    years_in_business = models.IntegerField()
    annual_revenue = models.DecimalField(max_digits=15, decimal_places=2)
    number_of_employees = models.IntegerField()
    
    # Financial Information
    bank_name = models.CharField(max_length=200)
    bank_account_number = models.CharField(max_length=50)
    bank_contact = models.CharField(max_length=200, blank=True)
    
    # Trade References
    trade_references = models.JSONField(default=list, blank=True)
    
    # Review Information
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    reviewed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    reviewed_date = models.DateTimeField(null=True, blank=True)
    review_notes = models.TextField(blank=True)
    
    # Approval Information
    approved_credit_limit = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True
    )
    approved_payment_terms = models.CharField(max_length=100, blank=True)
    
    class Meta:
        ordering = ['-application_date']
        db_table = 'finance_customer_credit_applications'
        
    def __str__(self):
        return f'{self.customer.name} - Credit Application ({self.status})'
    
    def approve_application(self, user, approved_limit, payment_terms):
        """Approve the credit application"""
        self.status = 'APPROVED'
        self.reviewed_by = user
        self.reviewed_date = timezone.now()
        self.approved_credit_limit = approved_limit
        self.approved_payment_terms = payment_terms
        self.save()
        
        # Update customer financial profile
        profile, created = CustomerFinancialProfile.objects.get_or_create(
            tenant=self.tenant,
            customer=self.customer
        )
        profile.credit_limit = approved_limit
        profile.payment_terms_days = int(payment_terms.split()[0]) if payment_terms.startswith('Net') else 30
        profile.save()
    
    def reject_application(self, user, reason):
        """Reject the credit application"""
        self.status = 'REJECTED'
        self.reviewed_by = user
        self.reviewed_date = timezone.now()
        self.review_notes = reason
        self.save()