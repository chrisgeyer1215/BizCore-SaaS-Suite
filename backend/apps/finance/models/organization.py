"""
Organization Models
Projects, departments, and locations for financial tracking
"""

from django.db import models
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.utils import timezone
from decimal import Decimal
from datetime import date

from apps.core.models import TenantBaseModel, SoftDeleteMixin
from apps.core.utils import generate_code
from .currency import Currency

User = get_user_model()


class Project(TenantBaseModel, SoftDeleteMixin):
    """Enhanced project tracking for job costing and profitability analysis"""
    
    STATUS_CHOICES = [
        ('PLANNING', 'Planning'),
        ('ACTIVE', 'Active'),
        ('ON_HOLD', 'On Hold'),
        ('COMPLETED', 'Completed'),
        ('CANCELLED', 'Cancelled'),
        ('ARCHIVED', 'Archived'),
    ]
    
    PROJECT_TYPES = [
        ('INTERNAL', 'Internal Project'),
        ('CLIENT', 'Client Project'),
        ('FIXED_PRICE', 'Fixed Price'),
        ('TIME_MATERIALS', 'Time & Materials'),
        ('RETAINER', 'Retainer'),
        ('SUPPORT', 'Support Contract'),
        ('RESEARCH', 'Research & Development'),
        ('MARKETING', 'Marketing Campaign'),
    ]
    
    BILLING_METHODS = [
        ('HOURLY', 'Hourly Rate'),
        ('FIXED', 'Fixed Price'),
        ('MILESTONE', 'Milestone Based'),
        ('EXPENSE_PLUS', 'Cost Plus'),
        ('NOT_BILLABLE', 'Not Billable'),
    ]
    
    # Project Information
    project_number = models.CharField(max_length=50)
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    project_type = models.CharField(max_length=20, choices=PROJECT_TYPES, default='CLIENT')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PLANNING')
    
    # Customer & Financial
    customer = models.ForeignKey(
        'crm.Customer',
        on_delete=models.CASCADE,
        related_name='projects'
    )
    currency = models.ForeignKey(Currency, on_delete=models.PROTECT)
    
    # Estimates
    estimated_hours = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    estimated_cost = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    estimated_revenue = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    budget = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    
    # Actuals
    actual_hours = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    actual_cost = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    actual_revenue = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    
    # Billing Configuration
    billing_method = models.CharField(max_length=20, choices=BILLING_METHODS, default='HOURLY')
    hourly_rate = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    markup_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'))
    
    # Dates
    start_date = models.DateField()
    estimated_end_date = models.DateField(null=True, blank=True)
    actual_end_date = models.DateField(null=True, blank=True)
    
    # Team & Management
    project_manager = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='managed_projects'
    )
    team_members = models.ManyToManyField(User, through='ProjectTeamMember', blank=True)
    
    # Progress Tracking
    completion_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'))
    
    # Project Categories
    department = models.ForeignKey(
        'finance.Department',
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    location = models.ForeignKey(
        'finance.Location',
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    
    # Settings
    track_time = models.BooleanField(default=True)
    track_expenses = models.BooleanField(default=True)
    billable = models.BooleanField(default=True)
    auto_invoice = models.BooleanField(default=False)
    
    # Contract Information
    contract_value = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    contract_start_date = models.DateField(null=True, blank=True)
    contract_end_date = models.DateField(null=True, blank=True)
    
    # Notes
    notes = models.TextField(blank=True)
    internal_notes = models.TextField(blank=True)
    
    # Tags for categorization
    tags = models.JSONField(default=list, blank=True)
    
    class Meta:
        ordering = ['-start_date']
        db_table = 'finance_projects'
        constraints = [
            models.UniqueConstraint(
                fields=['tenant', 'project_number'],
                name='unique_tenant_project_number'
            ),
        ]
        indexes = [
            models.Index(fields=['tenant', 'status', 'customer']),
            models.Index(fields=['tenant', 'project_manager']),
            models.Index(fields=['tenant', 'start_date']),
        ]
        
    def __str__(self):
        return f'{self.project_number} - {self.name}'
    
    def save(self, *args, **kwargs):
        if not self.project_number:
            self.project_number = self.generate_project_number()
        super().save(*args, **kwargs)
    
    def generate_project_number(self):
        """Generate unique project number"""
        return generate_code('PROJ', self.tenant_id)
    
    def clean(self):
        """Validate project"""
        if self.start_date and self.estimated_end_date:
            if self.start_date >= self.estimated_end_date:
                raise ValidationError('Start date must be before estimated end date')
        
        if self.actual_end_date and self.start_date:
            if self.actual_end_date < self.start_date:
                raise ValidationError('Actual end date cannot be before start date')
        
        if self.completion_percentage < 0 or self.completion_percentage > 100:
            raise ValidationError('Completion percentage must be between 0 and 100')
        
        if self.contract_start_date and self.contract_end_date:
            if self.contract_start_date >= self.contract_end_date:
                raise ValidationError('Contract start date must be before end date')
    
    @property
    def gross_profit(self):
        """Calculate gross profit"""
        return self.actual_revenue - self.actual_cost
    
    @property
    def profit_margin(self):
        """Calculate profit margin percentage"""
        if self.actual_revenue > 0:
            return (self.gross_profit / self.actual_revenue) * 100
        return Decimal('0.00')
    
    @property
    def cost_variance(self):
        """Calculate cost variance (actual vs estimated)"""
        if self.estimated_cost:
            return self.actual_cost - self.estimated_cost
        return Decimal('0.00')
    
    @property
    def revenue_variance(self):
        """Calculate revenue variance (actual vs estimated)"""
        if self.estimated_revenue:
            return self.actual_revenue - self.estimated_revenue
        return Decimal('0.00')
    
    @property
    def budget_utilization(self):
        """Calculate budget utilization percentage"""
        if self.budget and self.budget > 0:
            return (self.actual_cost / self.budget) * 100
        return Decimal('0.00')
    
    @property
    def is_over_budget(self):
        """Check if project is over budget"""
        if self.budget:
            return self.actual_cost > self.budget
        return False
    
    @property
    def days_remaining(self):
        """Calculate days remaining until estimated end date"""
        if self.estimated_end_date and self.status == 'ACTIVE':
            return (self.estimated_end_date - date.today()).days
        return None
    
    @property
    def is_overdue(self):
        """Check if project is overdue"""
        if self.estimated_end_date and self.status == 'ACTIVE':
            return date.today() > self.estimated_end_date
        return False
    
    def update_financials(self):
        """Update project financial summary from related transactions"""
        from ..services.project_costing import ProjectCostingService
        
        service = ProjectCostingService(self.tenant)
        service.update_project_costs(self)
    
    def calculate_completion_percentage(self):
        """Calculate completion percentage based on various factors"""
        if self.estimated_hours and self.actual_hours:
            hours_percentage = min(100, (self.actual_hours / self.estimated_hours) * 100)
        else:
            hours_percentage = 0
        
        if self.estimated_cost and self.actual_cost:
            cost_percentage = min(100, (self.actual_cost / self.estimated_cost) * 100)
        else:
            cost_percentage = 0
        
        # Use the average of hours and cost percentages
        if hours_percentage > 0 and cost_percentage > 0:
            self.completion_percentage = (hours_percentage + cost_percentage) / 2
        elif hours_percentage > 0:
            self.completion_percentage = hours_percentage
        elif cost_percentage > 0:
            self.completion_percentage = cost_percentage
        
        self.save(update_fields=['completion_percentage'])
    
    def close_project(self, user):
        """Close/complete the project"""
        self.status = 'COMPLETED'
        self.actual_end_date = date.today()
        self.completion_percentage = Decimal('100.00')
        self.save()
        
        # Update final financials
        self.update_financials()


class ProjectTeamMember(TenantBaseModel):
    """Project team member assignments with rates and roles"""
    
    ROLE_CHOICES = [
        ('MANAGER', 'Project Manager'),
        ('LEAD', 'Team Lead'),
        ('DEVELOPER', 'Developer'),
        ('DESIGNER', 'Designer'),
        ('ANALYST', 'Business Analyst'),
        ('CONSULTANT', 'Consultant'),
        ('QA', 'Quality Assurance'),
        ('ARCHITECT', 'Technical Architect'),
        ('COORDINATOR', 'Project Coordinator'),
        ('OTHER', 'Other'),
    ]
    
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='team_assignments')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='OTHER')
    
    # Billing Information
    hourly_rate = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    cost_rate = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    
    # Assignment Period
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    
    # Allocation
    allocation_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('100.00'),
        help_text="Percentage of time allocated to this project"
    )
    
    # Tracking
    hours_worked = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    total_cost = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    total_billed = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    
    class Meta:
        ordering = ['project', 'role', 'user']
        db_table = 'finance_project_team_members'
        constraints = [
            models.UniqueConstraint(
                fields=['project', 'user', 'start_date'],
                name='unique_project_user_assignment'
            ),
        ]
        
    def __str__(self):
        return f'{self.project.project_number} - {self.user.get_full_name()} ({self.role})'
    
    def clean(self):
        """Validate team member assignment"""
        if self.end_date and self.start_date >= self.end_date:
            raise ValidationError('Start date must be before end date')
        
        if self.allocation_percentage < 0 or self.allocation_percentage > 100:
            raise ValidationError('Allocation percentage must be between 0 and 100')
    
    @property
    def is_current(self):
        """Check if assignment is currently active"""
        today = date.today()
        if not self.is_active:
            return False
        if self.end_date and today > self.end_date:
            return False
        return today >= self.start_date
    
    @property
    def effective_hourly_rate(self):
        """Get effective hourly rate (project rate or user rate)"""
        return self.hourly_rate or self.project.hourly_rate or Decimal('0.00')


class Department(TenantBaseModel, SoftDeleteMixin):
    """Enhanced department/division tracking with budgets and cost centers"""
    
    DEPARTMENT_TYPES = [
        ('REVENUE', 'Revenue Department'),
        ('COST_CENTER', 'Cost Center'),
        ('PROFIT_CENTER', 'Profit Center'),
        ('SUPPORT', 'Support Department'),
    ]
    
    code = models.CharField(max_length=20)
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    department_type = models.CharField(max_length=20, choices=DEPARTMENT_TYPES, default='COST_CENTER')
    
    # Hierarchy
    parent_department = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='sub_departments'
    )
    level = models.PositiveSmallIntegerField(default=0)
    
    # Management
    manager = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='managed_departments'
    )
    cost_center = models.CharField(max_length=50, blank=True)
    
    # Budget Information
    annual_budget = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    current_year_actual = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    current_year_committed = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    
    # Revenue tracking (for profit centers)
    annual_revenue_target = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    current_year_revenue = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    
    # Default Accounts
    default_expense_account = models.ForeignKey(
        'finance.Account',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='departments_expense'
    )
    default_revenue_account = models.ForeignKey(
        'finance.Account',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='departments_revenue'
    )
    
    # Settings
    is_active = models.BooleanField(default=True)
    require_budget_approval = models.BooleanField(default=False)
    budget_approval_limit = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    
    # Contact Information
    phone = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    location = models.ForeignKey(
        'finance.Location',
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    
    class Meta:
        ordering = ['code']
        db_table = 'finance_departments'
        constraints = [
            models.UniqueConstraint(
                fields=['tenant', 'code'],
                name='unique_tenant_department_code'
            ),
        ]
        indexes = [
            models.Index(fields=['tenant', 'parent_department']),
            models.Index(fields=['tenant', 'manager']),
            models.Index(fields=['tenant', 'is_active']),
        ]
        
    def __str__(self):
        return f'{self.code} - {self.name}'
    
    def save(self, *args, **kwargs):
        # Auto-calculate level based on parent
        if self.parent_department:
            self.level = self.parent_department.level + 1
        else:
            self.level = 0
        
        super().save(*args, **kwargs)
    
    def clean(self):
        """Validate department"""
        # Prevent circular references
        if self.parent_department:
            current = self.parent_department
            while current:
                if current == self:
                    raise ValidationError('Circular reference detected in department hierarchy')
                current = current.parent_department
    
    @property
    def budget_utilization(self):
        """Calculate budget utilization percentage"""
        if self.annual_budget and self.annual_budget > 0:
            return (self.current_year_actual / self.annual_budget) * 100
        return Decimal('0.00')
    
    @property
    def budget_variance(self):
        """Calculate budget variance (actual vs budget)"""
        if self.annual_budget:
            return self.current_year_actual - self.annual_budget
        return Decimal('0.00')
    
    @property
    def available_budget(self):
        """Get remaining budget available"""
        if self.annual_budget:
            return self.annual_budget - self.current_year_actual - self.current_year_committed
        return Decimal('0.00')
    
    @property
    def revenue_variance(self):
        """Calculate revenue variance (actual vs target)"""
        if self.annual_revenue_target:
            return self.current_year_revenue - self.annual_revenue_target
        return Decimal('0.00')
    
    @property
    def profit_loss(self):
        """Calculate profit/loss for profit centers"""
        if self.department_type == 'PROFIT_CENTER':
            return self.current_year_revenue - self.current_year_actual
        return Decimal('0.00')
    
    def get_full_path(self):
        """Get full department hierarchy path"""
        path = [self.name]
        parent = self.parent_department
        while parent:
            path.insert(0, parent.name)
            parent = parent.parent_department
        return ' > '.join(path)
    
    def get_children(self, include_inactive=False):
        """Get all child departments"""
        queryset = self.sub_departments.all()
        if not include_inactive:
            queryset = queryset.filter(is_active=True)
        return queryset
    
    def get_descendants(self, include_inactive=False):
        """Get all descendant departments (recursive)"""
        descendants = []
        children = self.get_children(include_inactive)
        
        for child in children:
            descendants.append(child)
            descendants.extend(child.get_descendants(include_inactive))
        
        return descendants


class Location(TenantBaseModel, SoftDeleteMixin):
    """Enhanced location/branch tracking with multi-currency and cost allocation"""
    
    LOCATION_TYPES = [
        ('HEADQUARTERS', 'Headquarters'),
        ('BRANCH', 'Branch Office'),
        ('WAREHOUSE', 'Warehouse'),
        ('RETAIL', 'Retail Store'),
        ('MANUFACTURING', 'Manufacturing'),
        ('DISTRIBUTION', 'Distribution Center'),
        ('REMOTE', 'Remote Location'),
        ('VIRTUAL', 'Virtual Location'),
    ]
    
    code = models.CharField(max_length=20)
    name = models.CharField(max_length=100)
    location_type = models.CharField(max_length=20, choices=LOCATION_TYPES, default='BRANCH')
    
    # Address Information
    address = models.JSONField(default=dict)
    timezone = models.CharField(max_length=50, blank=True)
    
    # Contact Information
    phone = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    website = models.URLField(blank=True)
    
    # Management
    manager = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='managed_locations'
    )
    
    # Financial Configuration
    is_profit_center = models.BooleanField(default=False)
    currency = models.ForeignKey(Currency, on_delete=models.PROTECT, null=True, blank=True)
    
    # Operating Information
    operating_hours = models.JSONField(default=dict, blank=True)
    employee_count = models.PositiveIntegerField(default=0)
    square_footage = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    
    # Financial Tracking
    annual_operating_budget = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    current_year_expenses = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    current_year_revenue = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    
    # Cost Allocation
    rent_cost = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    utilities_cost = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    insurance_cost = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    
    # Settings
    is_active = models.BooleanField(default=True)
    tax_jurisdiction = models.ForeignKey(
        'finance.TaxJurisdiction',
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    
    # Integration
    external_location_id = models.CharField(max_length=100, blank=True)
    
    class Meta:
        ordering = ['code']
        db_table = 'finance_locations'
        constraints = [
            models.UniqueConstraint(
                fields=['tenant', 'code'],
                name='unique_tenant_location_code'
            ),
        ]
        indexes = [
            models.Index(fields=['tenant', 'location_type', 'is_active']),
            models.Index(fields=['tenant', 'manager']),
        ]
        
    def __str__(self):
        return f'{self.code} - {self.name}'
    
    def clean(self):
        """Validate location"""
        if self.square_footage and self.square_footage <= 0:
            raise ValidationError('Square footage must be positive')
        
        if self.employee_count < 0:
            raise ValidationError('Employee count cannot be negative')
    
    @property
    def cost_per_employee(self):
        """Calculate cost per employee"""
        if self.employee_count > 0:
            return self.current_year_expenses / self.employee_count
        return Decimal('0.00')
    
    @property
    def cost_per_square_foot(self):
        """Calculate cost per square foot"""
        if self.square_footage and self.square_footage > 0:
            return self.current_year_expenses / self.square_footage
        return Decimal('0.00')
    
    @property
    def budget_utilization(self):
        """Calculate budget utilization percentage"""
        if self.annual_operating_budget and self.annual_operating_budget > 0:
            return (self.current_year_expenses / self.annual_operating_budget) * 100
        return Decimal('0.00')
    
    @property
    def profit_loss(self):
        """Calculate profit/loss for profit centers"""
        if self.is_profit_center:
            return self.current_year_revenue - self.current_year_expenses
        return Decimal('0.00')
    
    @property
    def formatted_address(self):
        """Get formatted address string"""
        if not self.address:
            return ''
        
        parts = []
        for field in ['street', 'city', 'state', 'postal_code', 'country']:
            if self.address.get(field):
                parts.append(self.address[field])
        
        return ', '.join(parts)
    
    def calculate_overhead_allocation(self, allocation_base='EMPLOYEES'):
        """Calculate overhead allocation for this location"""
        if allocation_base == 'EMPLOYEES' and self.employee_count > 0:
            return self.current_year_expenses / self.employee_count
        elif allocation_base == 'SQUARE_FOOTAGE' and self.square_footage:
            return self.current_year_expenses / self.square_footage
        elif allocation_base == 'REVENUE' and self.current_year_revenue > 0:
            return self.current_year_expenses / self.current_year_revenue
        
        return Decimal('0.00')