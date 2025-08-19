"""
Budgeting and Planning Models
Budget templates, budgets, and variance analysis
"""

from django.db import models
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.utils import timezone
from decimal import Decimal
from datetime import date
import calendar

from apps.core.models import TenantBaseModel

User = get_user_model()


class BudgetTemplate(TenantBaseModel):
    """Budget templates for different entities and time periods"""
    
    TEMPLATE_TYPES = [
        ('ANNUAL', 'Annual Budget'),
        ('QUARTERLY', 'Quarterly Budget'),
        ('MONTHLY', 'Monthly Budget'),
        ('PROJECT', 'Project Budget'),
        ('DEPARTMENT', 'Department Budget'),
        ('LOCATION', 'Location Budget'),
        ('CASH_FLOW', 'Cash Flow Budget'),
    ]
    
    ENTITY_TYPES = [
        ('COMPANY', 'Company-wide'),
        ('DEPARTMENT', 'Department'),
        ('LOCATION', 'Location'),
        ('PROJECT', 'Project'),
        ('PRODUCT_LINE', 'Product Line'),
    ]
    
    name = models.CharField(max_length=200)
    template_type = models.CharField(max_length=20, choices=TEMPLATE_TYPES)
    entity_type = models.CharField(max_length=20, choices=ENTITY_TYPES)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    
    # Template Settings
    accounts = models.ManyToManyField('finance.Account', through='BudgetTemplateItem')
    
    # Version Control
    version = models.PositiveIntegerField(default=1)
    previous_version = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='newer_versions'
    )
    
    # Usage Tracking
    usage_count = models.PositiveIntegerField(default=0)
    last_used = models.DateTimeField(null=True, blank=True)
    
    # Creator
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    
    class Meta:
        ordering = ['name', '-version']
        db_table = 'finance_budget_templates'
        constraints = [
            models.UniqueConstraint(
                fields=['tenant', 'name', 'version'],
                name='unique_tenant_budget_template_version'
            ),
        ]
        
    def __str__(self):
        return f'{self.name} v{self.version}'
    
    def create_new_version(self, user):
        """Create a new version of this template"""
        new_template = BudgetTemplate.objects.create(
            tenant=self.tenant,
            name=self.name,
            template_type=self.template_type,
            entity_type=self.entity_type,
            description=self.description,
            version=self.version + 1,
            previous_version=self,
            created_by=user
        )
        
        # Copy template items
        for item in self.template_items.all():
            BudgetTemplateItem.objects.create(
                tenant=self.tenant,
                template=new_template,
                account=item.account,
                budget_amount=item.budget_amount,
                calculation_method=item.calculation_method,
                calculation_parameters=item.calculation_parameters,
                notes=item.notes
            )
        
        return new_template
    
    def apply_to_budget(self, budget):
        """Apply template to a budget"""
        for item in self.template_items.all():
            BudgetItem.objects.get_or_create(
                budget=budget,
                account=item.account,
                defaults={
                    'tenant': self.tenant,
                    'budget_amount': item.calculate_budget_amount(budget),
                    'notes': item.notes
                }
            )
        
        # Update usage tracking
        self.usage_count += 1
        self.last_used = timezone.now()
        self.save()


class BudgetTemplateItem(TenantBaseModel):
    """Individual accounts in budget templates with calculation methods"""
    
    CALCULATION_METHODS = [
        ('FIXED', 'Fixed Amount'),
        ('PERCENTAGE_OF_REVENUE', 'Percentage of Revenue'),
        ('PERCENTAGE_OF_EXPENSE', 'Percentage of Expense'),
        ('PER_EMPLOYEE', 'Per Employee'),
        ('PER_SQUARE_FOOT', 'Per Square Foot'),
        ('PRIOR_YEAR_PLUS', 'Prior Year Plus Amount'),
        ('PRIOR_YEAR_PERCENTAGE', 'Prior Year Plus Percentage'),
        ('FORMULA', 'Custom Formula'),
    ]
    
    template = models.ForeignKey(
        BudgetTemplate,
        on_delete=models.CASCADE,
        related_name='template_items'
    )
    account = models.ForeignKey('finance.Account', on_delete=models.CASCADE)
    
    # Budget Configuration
    budget_amount = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    calculation_method = models.CharField(max_length=30, choices=CALCULATION_METHODS, default='FIXED')
    calculation_parameters = models.JSONField(default=dict, blank=True)
    
    # Notes and Documentation
    notes = models.TextField(blank=True)
    
    # Ordering
    sort_order = models.IntegerField(default=0)
    
    class Meta:
        ordering = ['template', 'sort_order', 'account']
        db_table = 'finance_budget_template_items'
        constraints = [
            models.UniqueConstraint(
                fields=['template', 'account'],
                name='unique_template_account'
            ),
        ]
        
    def __str__(self):
        return f'{self.template.name} - {self.account.name}'
    
    def calculate_budget_amount(self, budget):
        """Calculate budget amount based on method and parameters"""
        if self.calculation_method == 'FIXED':
            return self.budget_amount
        
        elif self.calculation_method == 'PERCENTAGE_OF_REVENUE':
            percentage = Decimal(str(self.calculation_parameters.get('percentage', 0)))
            revenue_account_id = self.calculation_parameters.get('revenue_account_id')
            if revenue_account_id:
                try:
                    revenue_item = budget.budget_items.get(account_id=revenue_account_id)
                    return revenue_item.total_budget * (percentage / 100)
                except BudgetItem.DoesNotExist:
                    pass
            return Decimal('0.00')
        
        elif self.calculation_method == 'PER_EMPLOYEE':
            amount_per_employee = Decimal(str(self.calculation_parameters.get('amount', 0)))
            employee_count = self.calculation_parameters.get('employee_count', 0)
            return amount_per_employee * employee_count
        
        elif self.calculation_method == 'PRIOR_YEAR_PLUS':
            # This would need access to prior year actual amounts
            base_amount = Decimal(str(self.calculation_parameters.get('base_amount', 0)))
            additional_amount = Decimal(str(self.calculation_parameters.get('additional_amount', 0)))
            return base_amount + additional_amount
        
        elif self.calculation_method == 'PRIOR_YEAR_PERCENTAGE':
            base_amount = Decimal(str(self.calculation_parameters.get('base_amount', 0)))
            percentage_increase = Decimal(str(self.calculation_parameters.get('percentage', 0)))
            return base_amount * (1 + percentage_increase / 100)
        
        return self.budget_amount


class Budget(TenantBaseModel):
    """Actual budgets for specific periods and entities"""
    
    STATUS_CHOICES = [
        ('DRAFT', 'Draft'),
        ('PENDING_APPROVAL', 'Pending Approval'),
        ('APPROVED', 'Approved'),
        ('ACTIVE', 'Active'),
        ('CLOSED', 'Closed'),
        ('CANCELLED', 'Cancelled'),
    ]
    
    name = models.CharField(max_length=200)
    fiscal_year = models.ForeignKey('finance.FiscalYear', on_delete=models.CASCADE)
    start_date = models.DateField()
    end_date = models.DateField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='DRAFT')
    
    # Entity Assignment
    department = models.ForeignKey(
        'finance.Department',
        on_delete=models.CASCADE,
        null=True,
        blank=True
    )
    location = models.ForeignKey(
        'finance.Location',
        on_delete=models.CASCADE,
        null=True,
        blank=True
    )
    project = models.ForeignKey(
        'finance.Project',
        on_delete=models.CASCADE,
        null=True,
        blank=True
    )
    
    # Budget Totals
    total_revenue_budget = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    total_expense_budget = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    net_income_budget = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    
    # Approval Workflow
    submitted_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='submitted_budgets'
    )
    submitted_date = models.DateTimeField(null=True, blank=True)
    
    approved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_budgets'
    )
    approved_date = models.DateTimeField(null=True, blank=True)
    
    # Template Reference
    template = models.ForeignKey(
        BudgetTemplate,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    
    # Version Control
    version = models.PositiveIntegerField(default=1)
    parent_budget = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='revisions'
    )
    
    # Notes
    description = models.TextField(blank=True)
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-start_date', 'name']
        db_table = 'finance_budgets'
        constraints = [
            models.UniqueConstraint(
                fields=['tenant', 'name', 'fiscal_year', 'version'],
                name='unique_tenant_budget_version'
            ),
        ]
        indexes = [
            models.Index(fields=['tenant', 'fiscal_year', 'status']),
            models.Index(fields=['tenant', 'department']),
            models.Index(fields=['tenant', 'location']),
            models.Index(fields=['tenant', 'project']),
        ]
        
    def __str__(self):
        entity = self.department or self.location or self.project or 'Company'
        return f'{self.name} - {entity} ({self.start_date} to {self.end_date})'
    
    def clean(self):
        """Validate budget"""
        if self.start_date >= self.end_date:
            raise ValidationError('Start date must be before end date')
        
        # Check if dates are within fiscal year
        if not (self.fiscal_year.start_date <= self.start_date <= self.fiscal_year.end_date):
            raise ValidationError('Budget start date must be within the fiscal year')
        
        if not (self.fiscal_year.start_date <= self.end_date <= self.fiscal_year.end_date):
            raise ValidationError('Budget end date must be within the fiscal year')
    
    def calculate_totals(self):
        """Calculate budget totals from line items"""
        revenue_total = self.budget_items.filter(
            account__account_type__in=['REVENUE', 'OTHER_INCOME']
        ).aggregate(
            total=models.Sum('total_budget')
        )['total'] or Decimal('0.00')
        
        expense_total = self.budget_items.filter(
            account__account_type__in=['EXPENSE', 'COST_OF_GOODS_SOLD', 'OTHER_EXPENSE']
        ).aggregate(
            total=models.Sum('total_budget')
        )['total'] or Decimal('0.00')
        
        self.total_revenue_budget = revenue_total
        self.total_expense_budget = expense_total
        self.net_income_budget = revenue_total - expense_total
        
        self.save(update_fields=[
            'total_revenue_budget', 'total_expense_budget', 'net_income_budget'
        ])
    
    def submit_for_approval(self, user):
        """Submit budget for approval"""
        if self.status != 'DRAFT':
            raise ValidationError('Only draft budgets can be submitted for approval')
        
        self.status = 'PENDING_APPROVAL'
        self.submitted_by = user
        self.submitted_date = timezone.now()
        self.save()
    
    def approve_budget(self, user):
        """Approve the budget"""
        if self.status != 'PENDING_APPROVAL':
            raise ValidationError('Budget is not in pending approval status')
        
        self.status = 'APPROVED'
        self.approved_by = user
        self.approved_date = timezone.now()
        self.save()
    
    def activate_budget(self):
        """Activate the budget"""
        if self.status != 'APPROVED':
            raise ValidationError('Only approved budgets can be activated')
        
        self.status = 'ACTIVE'
        self.save()
    
    def create_revision(self, user):
        """Create a new revision of this budget"""
        new_budget = Budget.objects.create(
            tenant=self.tenant,
            name=self.name,
            fiscal_year=self.fiscal_year,
            start_date=self.start_date,
            end_date=self.end_date,
            department=self.department,
            location=self.location,
            project=self.project,
            version=self.version + 1,
            parent_budget=self,
            template=self.template,
            description=self.description,
            submitted_by=user
        )
        
        # Copy budget items
        for item in self.budget_items.all():
            BudgetItem.objects.create(
                tenant=self.tenant,
                budget=new_budget,
                account=item.account,
                january=item.january,
                february=item.february,
                march=item.march,
                april=item.april,
                may=item.may,
                june=item.june,
                july=item.july,
                august=item.august,
                september=item.september,
                october=item.october,
                november=item.november,
                december=item.december,
                notes=item.notes
            )
        
        new_budget.calculate_totals()
        return new_budget
    
    def get_variance_analysis(self, as_of_date=None):
        """Get budget vs actual variance analysis"""
        from ..services.reporting import BudgetVarianceService
        
        service = BudgetVarianceService(self.tenant)
        return service.get_variance_analysis(self, as_of_date)


class BudgetItem(TenantBaseModel):
    """Individual budget line items with monthly breakdown"""
    
    budget = models.ForeignKey(Budget, on_delete=models.CASCADE, related_name='budget_items')
    account = models.ForeignKey('finance.Account', on_delete=models.CASCADE)
    
    # Monthly Budget Amounts
    january = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    february = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    march = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    april = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    may = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    june = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    july = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    august = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    september = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    october = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    november = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    december = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    
    # Calculated totals
    total_budget = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    
    # Additional Information
    notes = models.TextField(blank=True)
    assumptions = models.TextField(blank=True)
    
    # Variance tracking
    ytd_actual = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    ytd_variance = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    
    # Allocation settings
    allocation_method = models.CharField(
        max_length=20,
        choices=[
            ('EQUAL', 'Equal Monthly'),
            ('SEASONAL', 'Seasonal Pattern'),
            ('WEIGHTED', 'Weighted Distribution'),
            ('MANUAL', 'Manual Entry'),
        ],
        default='MANUAL'
    )
    allocation_pattern = models.JSONField(default=list, blank=True)
    
    class Meta:
        ordering = ['budget', 'account']
        db_table = 'finance_budget_items'
        constraints = [
            models.UniqueConstraint(
                fields=['budget', 'account'],
                name='unique_budget_account'
            ),
        ]
        indexes = [
            models.Index(fields=['tenant', 'budget', 'account']),
        ]
        
    def save(self, *args, **kwargs):
        # Calculate total budget
        self.total_budget = (
            self.january + self.february + self.march + self.april +
            self.may + self.june + self.july + self.august +
            self.september + self.october + self.november + self.december
        )
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f'{self.budget.name} - {self.account.name}'
    
    def get_monthly_amounts(self):
        """Get monthly amounts as a list"""
        return [
            self.january, self.february, self.march, self.april,
            self.may, self.june, self.july, self.august,
            self.september, self.october, self.november, self.december
        ]
    
    def set_monthly_amounts(self, amounts):
        """Set monthly amounts from a list"""
        if len(amounts) != 12:
            raise ValueError('Must provide exactly 12 monthly amounts')
        
        month_fields = [
            'january', 'february', 'march', 'april',
            'may', 'june', 'july', 'august',
            'september', 'october', 'november', 'december'
        ]
        
        for i, field in enumerate(month_fields):
            setattr(self, field, amounts[i])
    
    def distribute_amount(self, total_amount, method='EQUAL'):
        """Distribute total amount across months using specified method"""
        if method == 'EQUAL':
            monthly_amount = total_amount / 12
            amounts = [monthly_amount] * 12
        
        elif method == 'SEASONAL' and self.allocation_pattern:
            # Use seasonal pattern (percentages that sum to 100)
            if len(self.allocation_pattern) == 12:
                amounts = []
                for percentage in self.allocation_pattern:
                    amounts.append(total_amount * (Decimal(str(percentage)) / 100))
            else:
                amounts = [total_amount / 12] * 12
        
        elif method == 'WEIGHTED' and self.allocation_pattern:
            # Use weighted distribution
            if len(self.allocation_pattern) == 12:
                total_weight = sum(self.allocation_pattern)
                amounts = []
                for weight in self.allocation_pattern:
                    amounts.append(total_amount * (Decimal(str(weight)) / total_weight))
            else:
                amounts = [total_amount / 12] * 12
        
        else:
            amounts = [total_amount / 12] * 12
        
        self.set_monthly_amounts(amounts)
        self.allocation_method = method
        self.save()
    
    def get_budget_for_month(self, month, year=None):
        """Get budget amount for specific month"""
        if year and year != self.budget.fiscal_year.year:
            return Decimal('0.00')
        
        month_names = [
            'january', 'february', 'march', 'april',
            'may', 'june', 'july', 'august',
            'september', 'october', 'november', 'december'
        ]
        
        if 1 <= month <= 12:
            field_name = month_names[month - 1]
            return getattr(self, field_name)
        
        return Decimal('0.00')
    
    def get_ytd_budget(self, as_of_month=None):
        """Get year-to-date budget amount"""
        if not as_of_month:
            as_of_month = date.today().month
        
        monthly_amounts = self.get_monthly_amounts()
        return sum(monthly_amounts[:as_of_month])
    
    def update_variance(self, actual_amount=None):
        """Update variance calculations"""
        if actual_amount is not None:
            self.ytd_actual = actual_amount
        
        ytd_budget = self.get_ytd_budget()
        self.ytd_variance = self.ytd_actual - ytd_budget
        self.save(update_fields=['ytd_actual', 'ytd_variance'])
    
    @property
    def variance_percentage(self):
        """Calculate variance percentage"""
        ytd_budget = self.get_ytd_budget()
        if ytd_budget > 0:
            return (self.ytd_variance / ytd_budget) * 100
        return Decimal('0.00')
    
    @property
    def is_over_budget(self):
        """Check if over budget for the year to date"""
        return self.ytd_variance > 0 and self.account.account_type in [
            'EXPENSE', 'COST_OF_GOODS_SOLD', 'OTHER_EXPENSE'
        ]


class BudgetRevision(TenantBaseModel):
    """Track budget revisions and changes"""
    
    REVISION_TYPES = [
        ('ADJUSTMENT', 'Budget Adjustment'),
        ('REFORECAST', 'Reforecast'),
        ('SUPPLEMENT', 'Supplemental Budget'),
        ('TRANSFER', 'Budget Transfer'),
    ]
    
    budget = models.ForeignKey(Budget, on_delete=models.CASCADE, related_name='revisions')
    revision_type = models.CharField(max_length=20, choices=REVISION_TYPES)
    revision_date = models.DateField()
    
    # Change Details
    description = models.TextField()
    reason = models.TextField()
    amount_changed = models.DecimalField(max_digits=15, decimal_places=2)
    
    # Affected accounts
    accounts_affected = models.ManyToManyField('finance.Account', through='BudgetRevisionItem')
    
    # Approval
    requested_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='requested_budget_revisions'
    )
    approved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_budget_revisions'
    )
    approved_date = models.DateTimeField(null=True, blank=True)
    
    # Status
    is_approved = models.BooleanField(default=False)
    is_applied = models.BooleanField(default=False)
    
    class Meta:
        ordering = ['-revision_date']
        db_table = 'finance_budget_revisions'
        
    def __str__(self):
        return f'{self.budget.name} - {self.revision_type} ({self.revision_date})'
    
    def apply_revision(self):
        """Apply the revision to the budget"""
        if not self.is_approved:
            raise ValidationError('Revision must be approved before applying')
        
        if self.is_applied:
            raise ValidationError('Revision has already been applied')
        
        # Apply changes to budget items
        for revision_item in self.revision_items.all():
            budget_item, created = BudgetItem.objects.get_or_create(
                budget=self.budget,
                account=revision_item.account,
                defaults={'tenant': self.tenant}
            )
            
            # Apply the change amount
            if revision_item.month:
                current_amount = budget_item.get_budget_for_month(revision_item.month)
                new_amount = current_amount + revision_item.change_amount
                
                month_names = [
                    'january', 'february', 'march', 'april',
                    'may', 'june', 'july', 'august',
                    'september', 'october', 'november', 'december'
                ]
                
                if 1 <= revision_item.month <= 12:
                    field_name = month_names[revision_item.month - 1]
                    setattr(budget_item, field_name, new_amount)
                    budget_item.save()
            else:
                # Apply to all months equally
                monthly_change = revision_item.change_amount / 12
                amounts = budget_item.get_monthly_amounts()
                new_amounts = [amount + monthly_change for amount in amounts]
                budget_item.set_monthly_amounts(new_amounts)
                budget_item.save()
        
        # Update budget totals
        self.budget.calculate_totals()
        
        # Mark as applied
        self.is_applied = True
        self.save()


class BudgetRevisionItem(TenantBaseModel):
    """Individual account changes in budget revisions"""
    
    revision = models.ForeignKey(
        BudgetRevision,
        on_delete=models.CASCADE,
        related_name='revision_items'
    )
    account = models.ForeignKey('finance.Account', on_delete=models.CASCADE)
    
    # Change details
    change_amount = models.DecimalField(max_digits=15, decimal_places=2)
    month = models.PositiveSmallIntegerField(null=True, blank=True)  # 1-12, null for all months
    
    # Previous and new values
    previous_amount = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    new_amount = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    
    # Justification
    justification = models.TextField(blank=True)
    
    class Meta:
        ordering = ['revision', 'account']
        db_table = 'finance_budget_revision_items'
        
    def __str__(self):
        month_str = f' (Month {self.month})' if self.month else ''
        return f'{self.revision} - {self.account.name}{month_str}: {self.change_amount}'
    
    def clean(self):
        """Validate revision item"""
        if self.month and (self.month < 1 or self.month > 12):
            raise ValidationError('Month must be between 1 and 12')


class BudgetAlert(TenantBaseModel):
    """Budget alerts and notifications"""
    
    ALERT_TYPES = [
        ('OVER_BUDGET', 'Over Budget'),
        ('APPROACHING_LIMIT', 'Approaching Budget Limit'),
        ('VARIANCE_THRESHOLD', 'Variance Threshold Exceeded'),
        ('APPROVAL_REQUIRED', 'Approval Required'),
        ('REVISION_NEEDED', 'Revision Needed'),
    ]
    
    SEVERITY_LEVELS = [
        ('INFO', 'Information'),
        ('WARNING', 'Warning'),
        ('CRITICAL', 'Critical'),
        ('URGENT', 'Urgent'),
    ]
    
    budget = models.ForeignKey(Budget, on_delete=models.CASCADE, related_name='alerts')
    account = models.ForeignKey(
        'finance.Account',
        on_delete=models.CASCADE,
        null=True,
        blank=True
    )
    
    # Alert Details
    alert_type = models.CharField(max_length=30, choices=ALERT_TYPES)
    severity = models.CharField(max_length=20, choices=SEVERITY_LEVELS)
    message = models.TextField()
    
    # Thresholds
    threshold_amount = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    threshold_percentage = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    
    # Status
    is_active = models.BooleanField(default=True)
    is_acknowledged = models.BooleanField(default=False)
    acknowledged_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    acknowledged_date = models.DateTimeField(null=True, blank=True)
    
    # Recipients
    notify_users = models.ManyToManyField(User, blank=True)
    notify_emails = models.JSONField(default=list, blank=True)
    
    class Meta:
        ordering = ['-created_at']
        db_table = 'finance_budget_alerts'
        
    def __str__(self):
        return f'{self.budget.name} - {self.alert_type} ({self.severity})'
    
    def acknowledge(self, user):
        """Acknowledge the alert"""
        self.is_acknowledged = True
        self.acknowledged_by = user
        self.acknowledged_date = timezone.now()
        self.save()
    
    def send_notifications(self):
        """Send alert notifications to specified recipients"""
        from ..services.notifications import BudgetAlertService
        
        service = BudgetAlertService(self.tenant)
        return service.send_alert_notifications(self)